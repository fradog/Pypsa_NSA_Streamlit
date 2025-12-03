# -*- coding: utf-8 -*-
"""
Created on Sun Nov 30 16:55:05 2025

@author: dhfra
"""
import streamlit as st
import pypsa
import pandas as pd
import numpy as np

st.title("PyPSA Constraint Isolation Test")

# 1. Setup a single snapshot network
n = pypsa.Network()
snapshots = pd.to_datetime(['2024-01-01 00:00'])
n.set_snapshots(snapshots)

# 2. Add components: Demand 100 MW
n.add("Bus", "Southwest Bus")
n.add("Load", "National Load", bus="Southwest Bus", p_set=100.0) # 100 MW demand

# 3. Add a generator with a forced minimum capacity build
# p_max_pu is 1.0 (always available), capital_cost is low
n.add("Generator", "Test Generator",
      bus="Southwest Bus", 
      capital_cost=10, 
      marginal_cost=0, 
      p_nom_min=100.0, # <--- MUST BUILD 100 MW
      p_max_pu=pd.Series(1.0, index=snapshots), 
      carrier="test")

# 4. Add load shedding for feasibility backup
n.add("Generator", "Load Shedding",
      bus="Southwest Bus",
      p_nom_extendable=True,
      marginal_cost=100000 
      )

# 5. Optimize
st.header("Running Optimization (GLPK/CBC)...")
try:
    n.optimize(solver_name="cbc") # Using cbc as it installed previously
    st.success(f"Optimization successful: {n.model.status}")
except Exception as e:
    st.error(f"Optimization failed: {e}")

# 6. Display results
if n.model.status == 'ok':
    test_capacity = n.generators['p_nom_opt']["Test Generator"]
    shedding_capacity = n.generators['p_nom_opt']["Load Shedding"]
    
    st.header("Optimal Capacities (MW)")
    st.metric("Test Generator Capacity (Expected 100 MW)", f"{test_capacity:.2f} MW")
    st.metric("Load Shedding Capacity (Expected 0 MW)", f"{shedding_capacity:.2f} MW")
else:
    st.warning("Solver failed to return OK status.")


