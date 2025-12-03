# -*- coding: utf-8 -*-
"""
Created on Sun Nov 30 16:55:05 2025

@author: dhfra
"""
import streamlit as st
import pypsa
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os # Added for file path management

# Set Streamlit page configuration
st.set_page_config(page_title="PyPSA National Solar Array Model", layout="wide")

st.title("National Solar Array Optimization Results")

# --- 1. Network Setup ---
# Use 2013 (non-leap year) for standard 8760 hour TMY modeling
n = pypsa.Network()
hours_in_year = pd.date_range(start="2013-01-01T00:00",
                              end="2013-12-31T23:00",
                              freq="h") 
n.set_snapshots(hours_in_year)

# 1b. Load the NREL GHI data and process it
try:
    file_path = 'nrel_data/nsrdb_v4_2024.csv'
    if os.path.exists(file_path):
        st.info(f"Loading NREL data from {file_path}")
        ghi_data = pd.read_csv(file_path)
        ghi_data.columns = ghi_data.columns.str.strip()
        ghi_data.index = pd.to_datetime(ghi_data[['Year', 'Month', 'Day', 'Hour', 'Minute']])
        ghi_data['GHI'] = pd.to_numeric(ghi_data['GHI'], errors='coerce') 
        
        REFERENCE_IRRADIANCE = 1000 # W/m^2
        SYSTEM_EFFICIENCY = 0.85    

        hourly_capacity_factor = (ghi_data['GHI'] / REFERENCE_IRRADIANCE) * SYSTEM_EFFICIENCY
        hourly_capacity_factor = hourly_capacity_factor.clip(upper=1.0).fillna(0)

        # Shift index from 00:30:00 to 00:00:00
        hourly_capacity_factor.index = hourly_capacity_factor.index - pd.Timedelta(minutes=30)
        
        # --- FIX: Ensure leap day is dropped BEFORE reindexing to snapshots ---
        if len(hourly_capacity_factor) == 8784:
            st.warning("Leap year data detected. Removing February 29th for 8760 hour TMY alignment.")
            hourly_capacity_factor = hourly_capacity_factor[~((hourly_capacity_factor.index.month == 2) & (hourly_capacity_factor.index.day == 29))]
        
        # Now replace the years (2024) with the PyPSA network's year (2013)
        hourly_capacity_factor.index = n.snapshots
        
    else:
        st.error(f"Data file not found at {file_path}. Using placeholder data.")
        # ... (Fallback random data handling code remains the same) ...
        np.random.seed(42)
        random_cf = pd.Series(np.random.rand(len(n.snapshots)), index=n.snapshots)
        random_cf[n.snapshots.hour < 6] = 0
        random_cf[random_cf.index.hour > 18] = 0
        hourly_capacity_factor = random_cf

except Exception as e:
    st.error(f"An error occurred during data loading: {e}")
    # Fallback to empty series to prevent script crash
    hourly_capacity_factor = pd.Series(0.0, index=n.snapshots)


# --- 2. Add Components (Using aggressive costs to force investment) ---
n.add("Bus", "Southwest Bus", carrier="AC")
demand_profile = pd.Series(100.0, index=n.snapshots)
n.add("Load", "National Load", bus="Southwest Bus", p_set=demand_profile)

n.add("Generator", "National Solar",
      bus="Southwest Bus", capital_cost=500, marginal_cost=10, p_nom_max=100000,
      p_nom_min=100, # FORCING MINIMUM BUILD OF 100 MW
      p_max_pu=hourly_capacity_factor, 
      carrier="solar")

# --- ADD THE BATTERY BACK IN ---
n.add("StorageUnit", "National Battery",
      bus="Southwest Bus", 
      capital_cost=300, # e.g., $300/kWh 
      marginal_cost=0, 
      p_nom_max=50000,
      p_nom_min=0, # Let the optimizer decide how much power capacity to build
      max_hours=6, # e.g., 6 hours duration
      carrier="battery")
# --------------------------------

# Add a load shedder just for mathematical feasibility of the dispatch problem
n.add("Generator", "Load Shedding",
      bus="Southwest Bus",
      carrier="shedding",
      p_nom_extendable=True,
      marginal_cost=100000 # Cost of unserved energy (blackout)
      )

# --- 3. Optimize the network ---
st.header("Running Optimization (GLPK Solver)...")
with st.spinner('Solving the linear optimization problem. This may take a moment...'):
    try:
        n.optimize(solver_name="Glpk")
        st.success(f"Optimization successful: {n.model.status}")
    except Exception as e:
        st.error(f"Optimization failed: {e}")


# --- 4. Analyze results and display in Streamlit ---
st.header("Optimal Capacities (MW)")

if n.model.status == 'ok' or n.model.status == 'warning':
    solar_capacity = n.generators['p_nom_opt']["National Solar"]
    
    st.metric("Optimal Solar Capacity", f"{solar_capacity:.2f} MW")

    # --- 5. Plotting using Streamlit's built-in chart functionality ---
    st.header("Energy Balance Time Series (First Week)")

    try:
        generation_p = n.generators_t.p
        load_p = n.loads_t.p.sum(axis=1)

        plot_data = pd.DataFrame({
            'Solar': generation_p.get('National Solar', 0),
            'Demand': load_p
        })
        
        # Display only the first week for a readable plot in Streamlit
        st.line_chart(plot_data.head(24 * 7)) 

    except Exception as e:
        st.error(f"Plotting error: {e}")
        st.write("Check if optimization was successful.")

else:
    st.warning("Cannot display results because optimization did not return an 'ok' status.")

