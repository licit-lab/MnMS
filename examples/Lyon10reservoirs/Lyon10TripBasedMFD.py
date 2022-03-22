import pandas as pd

# Unimodal MFD of Lyon with 10 reservoirs, see Mariotte et al. 2020
data_MFD = pd.read_csv('MFD_10_201802.csv')


def V_MFD_res(n, i_res):  # Mean car_layer speed a function of car_layer accumulation
    Pc = data_MFD["Pc"][i_res]
    nc = data_MFD["nc"][i_res]
    njam = data_MFD["njam"][i_res]
    v = 0  # speed in m/s
    if n <= nc:
        v = Pc * (2 * nc - n) / nc ** 2
    elif nc < n < njam:
        v = Pc * (njam - n) * (njam + n - 2 * nc) / (njam - nc) ** 2 / n
    return v


def res_fct(dict_accumulations, i_res):
    v_car = V_MFD_res(dict_accumulations['car_layer'], i_res)
    v_car = max(v_car, 0.001)  # avoid gridlock
    v_bus = 0.15 * v_car + 10 / 3.6  # from Loder et al. 2017 (Empirics of multi-modal traffic networks)
    v_metro = 6 #dummy
    v_tram = 5 #dummy
    dict_speeds = {'car_layer': v_car, 'bus': v_bus, 'metro': v_metro, 'tram': v_tram}
    return dict_speeds