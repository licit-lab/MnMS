import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Unimodal MFD of Lyon with 10 reservoirs, see Mariotte et al. 2020
data_MFD = pd.read_csv('MFD_10_201802.csv')

def V_MFD_res(n, i_res): # Mean car speed a function of car accumulation
    Pc = data_MFD["Pc"][i_res]
    nc = data_MFD["nc"][i_res]
    njam = data_MFD["njam"][i_res]
    p = 0 # production
    if n<=nc:
        p = Pc*(2*nc-n)/nc**2
    elif n>nc and n<njam:
        p = Pc * (njam-n) * (njam+n-2*nc) / (njam-nc)**2 / n
    return p

def res_fct(dict_accumulations, i_res):
    V_car = V_MFD_res(dict_accumulations['car'], i_res)
    V_car = max(V_car, 0.001) # avoid gridlock
    V_bus = 4 # dummy
    dict_speeds = {'car': V_car, 'bus': V_bus}
    return dict_speeds

list_MFD_fct = []
for i in range(10):
    list_MFD_fct.append(lambda dict_acc : res_fct(dict_acc, i))
