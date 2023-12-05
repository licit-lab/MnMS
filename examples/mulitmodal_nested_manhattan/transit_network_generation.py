from mnms.time import TimeTable, Time, Dt

def generate_daganzo_hybrid_transit_network_stops(roads):
    ### Add nodes and sections not connected to the rest of the roads for the train line
    roads.register_node('Rail_1',[15000,28000])
    roads.register_node('Rail_2', [15000,24000])
    roads.register_node('Rail_3', [15000,20000])
    roads.register_node('Rail_4', [15000,15000])
    roads.register_node('Rail_5', [15000,10000])
    roads.register_node('Rail_6', [15000,6000])
    roads.register_node('Rail_7', [15000,2000])
    roads.register_node('Rail_8', [2000,15000])
    roads.register_node('Rail_9', [6000,15000])
    roads.register_node('Rail_10', [10000,15000])
    roads.register_node('Rail_11', [20000,15000])
    roads.register_node('Rail_12', [24000,15000])
    roads.register_node('Rail_13', [28000,15000])

    roads.register_section('Rail_1_Rail_2', 'Rail_1', 'Rail_2', 4000)
    roads.register_section('Rail_2_Rail_3', 'Rail_2', 'Rail_3', 4000)
    roads.register_section('Rail_3_Rail_4', 'Rail_3', 'Rail_4', 5000)
    roads.register_section('Rail_4_Rail_5', 'Rail_4', 'Rail_5', 5000)
    roads.register_section('Rail_5_Rail_6', 'Rail_5', 'Rail_6', 4000)
    roads.register_section('Rail_6_Rail_7', 'Rail_6', 'Rail_7', 4000)
    roads.register_section('Rail_7_Rail_6', 'Rail_7', 'Rail_6', 4000)
    roads.register_section('Rail_6_Rail_5', 'Rail_6', 'Rail_5', 4000)
    roads.register_section('Rail_5_Rail_4', 'Rail_5', 'Rail_4', 5000)
    roads.register_section('Rail_4_Rail_3', 'Rail_4', 'Rail_3', 4000)
    roads.register_section('Rail_3_Rail_2', 'Rail_3', 'Rail_2', 4000)
    roads.register_section('Rail_2_Rail_1', 'Rail_2', 'Rail_1', 4000)

    roads.register_section('Rail_8_Rail_9', 'Rail_8', 'Rail_9', 4000)
    roads.register_section('Rail_9_Rail_10', 'Rail_9', 'Rail_10', 4000)
    roads.register_section('Rail_10_Rail_4', 'Rail_10', 'Rail_4', 5000)
    roads.register_section('Rail_4_Rail_11', 'Rail_4', 'Rail_11', 4000)
    roads.register_section('Rail_11_Rail_12', 'Rail_11', 'Rail_12', 4000)
    roads.register_section('Rail_12_Rail_13', 'Rail_12', 'Rail_13', 4000)
    roads.register_section('Rail_13_Rail_12', 'Rail_13', 'Rail_12', 4000)
    roads.register_section('Rail_12_Rail_11', 'Rail_12', 'Rail_11', 4000)
    roads.register_section('Rail_11_Rail_4', 'Rail_11', 'Rail_4', 4000)
    roads.register_section('Rail_4_Rail_10', 'Rail_4', 'Rail_10', 5000)
    roads.register_section('Rail_10_Rail_9', 'Rail_10', 'Rail_9', 4000)
    roads.register_section('Rail_9_Rail_8', 'Rail_9', 'Rail_8', 4000)

    ## Add new nodes and sections under these new ones to allow cars and avs serve train stations
    # North
    roads.register_node('uz0_126b', [15000, 28000])
    roads.register_section('uz0_126_uz0_126b', 'uz0_126', 'uz0_126b', 1000)
    roads.register_section('uz0_126b_uz0_142', 'uz0_126b', 'uz0_142', 1000)
    roads.register_section('uz0_142_uz0_126b', 'uz0_142', 'uz0_126b', 1000)
    roads.register_section('uz0_126b_uz0_126', 'uz0_126b', 'uz0_126', 1000)
    roads.delete_section('uz0_126_uz0_142')
    roads.delete_section('uz0_142_uz0_126')

    roads.register_node('uz0_124b', [15000, 24000])
    roads.register_section('uz0_124_uz0_124b', 'uz0_124', 'uz0_124b', 1000)
    roads.register_section('uz0_124b_uz0_140', 'uz0_124b', 'uz0_140', 1000)
    roads.register_section('uz0_140_uz0_124b', 'uz0_140', 'uz0_124b', 1000)
    roads.register_section('uz0_124b_uz0_124', 'uz0_124b', 'uz0_124', 1000)
    roads.delete_section('uz0_124_uz0_140')
    roads.delete_section('uz0_140_uz0_124')

    # South
    roads.register_node('uz0_115b', [15000, 6000])
    roads.register_section('uz0_115_uz0_115b', 'uz0_115', 'uz0_115b', 1000)
    roads.register_section('uz0_115b_uz0_131', 'uz0_115b', 'uz0_131', 1000)
    roads.register_section('uz0_131_uz0_115b', 'uz0_131', 'uz0_115b', 1000)
    roads.register_section('uz0_115b_uz0_115', 'uz0_115b', 'uz0_115', 1000)
    roads.delete_section('uz0_115_uz0_131')
    roads.delete_section('uz0_131_uz0_115')

    roads.register_node('uz0_113b', [15000, 2000])
    roads.register_section('uz0_113_uz0_113b', 'uz0_113', 'uz0_113b', 1000)
    roads.register_section('uz0_113b_uz0_129', 'uz0_113b', 'uz0_129', 1000)
    roads.register_section('uz0_129_uz0_113b', 'uz0_129', 'uz0_113b', 1000)
    roads.register_section('uz0_113b_uz0_113', 'uz0_113b', 'uz0_113', 1000)
    roads.delete_section('uz0_113_uz0_129')
    roads.delete_section('uz0_129_uz0_113')

    # West
    roads.register_node('uz0_23b', [2000, 15000])
    roads.register_section('uz0_24_uz0_23b', 'uz0_24', 'uz0_23b', 1000)
    roads.register_section('uz0_23b_uz0_23', 'uz0_23b', 'uz0_23', 1000)
    roads.register_section('uz0_23_uz0_23b', 'uz0_23', 'uz0_23b', 1000)
    roads.register_section('uz0_23b_uz0_24', 'uz0_23b', 'uz0_24', 1000)
    roads.delete_section('uz0_23_uz0_24')
    roads.delete_section('uz0_24_uz0_23')

    roads.register_node('uz0_55b', [6000, 15000])
    roads.register_section('uz0_56_uz0_55b', 'uz0_56', 'uz0_55b', 1000)
    roads.register_section('uz0_55b_uz0_55', 'uz0_55b', 'uz0_55', 1000)
    roads.register_section('uz0_55_uz0_55b', 'uz0_55', 'uz0_55b', 1000)
    roads.register_section('uz0_55b_uz0_56', 'uz0_55b', 'uz0_56', 1000)
    roads.delete_section('uz0_55_uz0_56')
    roads.delete_section('uz0_56_uz0_55')

    # East
    roads.register_node('uz0_199b', [24000, 15000])
    roads.register_section('uz0_200_uz0_199b', 'uz0_200', 'uz0_199b', 1000)
    roads.register_section('uz0_199b_uz0_199', 'uz0_199b', 'uz0_199', 1000)
    roads.register_section('uz0_199_uz0_199b', 'uz0_199', 'uz0_199b', 1000)
    roads.register_section('uz0_199b_uz0_200', 'uz0_199b', 'uz0_200', 1000)
    roads.delete_section('uz0_199_uz0_200')
    roads.delete_section('uz0_200_uz0_199')

    roads.register_node('uz0_231b', [28000, 15000])
    roads.register_section('uz0_232_uz0_231b', 'uz0_232', 'uz0_231b', 1000)
    roads.register_section('uz0_231b_uz0_231', 'uz0_231b', 'uz0_231', 1000)
    roads.register_section('uz0_231_uz0_231b', 'uz0_231', 'uz0_231b', 1000)
    roads.register_section('uz0_231b_uz0_232', 'uz0_231b', 'uz0_232', 1000)
    roads.delete_section('uz0_231_uz0_232')
    roads.delete_section('uz0_232_uz0_231')

    ### Bus
    ## North->South
    # Bus North-South 1
    roads.register_stop('Bus_NS1_0', 'uz1_44_uz1_43', 0.)
    roads.register_stop('Bus_NS1_1', 'uz1_57_uz1_56', 0.)
    roads.register_stop('Bus_NS1_2', 'uz2_12_uz2_11', 0.)
    roads.register_stop('Bus_NS1_3', 'uz2_10_uz2_9', 0.)
    roads.register_stop('Bus_NS1_4', 'uz2_8_uz2_7', 0.)
    roads.register_stop('Bus_NS1_5', 'uz2_6_uz2_5', 0.)
    roads.register_stop('Bus_NS1_6', 'uz2_4_uz2_3', 0.)
    roads.register_stop('Bus_NS1_7', 'uz2_2_uz2_1', 0.)
    roads.register_stop('Bus_NS1_8', 'uz2_0_uz1_49', 0.)
    roads.register_stop('Bus_NS1_9', 'uz1_47_uz1_32', 0.)
    roads.register_stop('Bus_NS1_10', 'uz1_30_uz0_83', 0.)
    # Bus North-South 2
    roads.register_stop('Bus_NS2_0', 'uz2_38_uz2_37', 0.)
    roads.register_stop('Bus_NS2_1', 'uz2_36_uz2_35', 0.)
    roads.register_stop('Bus_NS2_2', 'uz2_34_uz2_33', 0.)
    roads.register_stop('Bus_NS2_3', 'uz2_32_uz2_31', 0.)
    roads.register_stop('Bus_NS2_4', 'uz2_30_uz2_29', 0.)
    roads.register_stop('Bus_NS2_5', 'uz2_28_uz2_27', 0.)
    roads.register_stop('Bus_NS2_6', 'uz2_26_uz1_78', 0.)
    # Bus North-South 3
    roads.register_stop('Bus_NS3_0', 'uz1_74_uz1_73', 0.)
    roads.register_stop('Bus_NS3_1', 'uz1_87_uz1_86', 0.)
    roads.register_stop('Bus_NS3_2', 'uz2_64_uz2_63', 0.)
    roads.register_stop('Bus_NS3_3', 'uz2_62_uz2_61', 0.)
    roads.register_stop('Bus_NS3_4', 'uz2_60_uz2_59', 0.)
    roads.register_stop('Bus_NS3_5', 'uz2_58_uz2_57', 0.)
    roads.register_stop('Bus_NS3_6', 'uz2_56_uz2_55', 0.)
    roads.register_stop('Bus_NS3_7', 'uz2_54_uz2_53', 0.)
    roads.register_stop('Bus_NS3_8', 'uz2_52_uz2_39', 0.)
    roads.register_stop('Bus_NS3_9', 'uz1_77_uz1_62', 0.)
    roads.register_stop('Bus_NS3_10', 'uz1_60_uz0_99', 0.)
    # Bus North-South 4
    roads.register_stop('Bus_NS4_0', 'uz1_164_uz1_163', 0.)
    roads.register_stop('Bus_NS4_1', 'uz1_147_uz1_146', 0.)
    roads.register_stop('Bus_NS4_2', 'uz2_116_uz2_115', 0.)
    roads.register_stop('Bus_NS4_3', 'uz2_114_uz2_113', 0.)
    roads.register_stop('Bus_NS4_4', 'uz2_112_uz2_111', 0.)
    roads.register_stop('Bus_NS4_5', 'uz2_110_uz2_109', 0.)
    roads.register_stop('Bus_NS4_6', 'uz2_108_uz2_107', 0.)
    roads.register_stop('Bus_NS4_7', 'uz2_106_uz2_105', 0.)
    roads.register_stop('Bus_NS4_8', 'uz2_104_uz2_117', 0.)
    roads.register_stop('Bus_NS4_9', 'uz1_137_uz1_152', 0.)
    roads.register_stop('Bus_NS4_10', 'uz1_150_uz0_147', 0.)
    # Bus North-South 5
    roads.register_stop('Bus_NS5_0', 'uz2_142_uz2_141', 0.)
    roads.register_stop('Bus_NS5_1', 'uz2_140_uz2_139', 0.)
    roads.register_stop('Bus_NS5_2', 'uz2_138_uz2_137', 0.)
    roads.register_stop('Bus_NS5_3', 'uz2_136_uz2_135', 0.)
    roads.register_stop('Bus_NS5_4', 'uz2_134_uz2_133', 0.)
    roads.register_stop('Bus_NS5_5', 'uz2_132_uz2_131', 0.)
    roads.register_stop('Bus_NS5_6', 'uz2_130_uz1_138', 0.)
    # Bus North-South 6
    roads.register_stop('Bus_NS6_0', 'uz1_194_uz1_193', 0.)
    roads.register_stop('Bus_NS6_1', 'uz1_177_uz1_176', 0.)
    roads.register_stop('Bus_NS6_2', 'uz2_168_uz2_167', 0.)
    roads.register_stop('Bus_NS6_3', 'uz2_166_uz2_165', 0.)
    roads.register_stop('Bus_NS6_4', 'uz2_164_uz2_163', 0.)
    roads.register_stop('Bus_NS6_5', 'uz2_162_uz2_161', 0.)
    roads.register_stop('Bus_NS6_6', 'uz2_160_uz2_159', 0.)
    roads.register_stop('Bus_NS6_7', 'uz2_158_uz2_157', 0.)
    roads.register_stop('Bus_NS6_8', 'uz2_156_uz1_169', 0.)
    roads.register_stop('Bus_NS6_9', 'uz1_167_uz1_182', 0.)
    roads.register_stop('Bus_NS6_10', 'uz1_180_uz0_163', 0.)
    ## Sout->North
    # Bus South-North 1
    roads.register_stop('Bus_SN1_0', 'uz1_30_uz1_31', 0.)
    roads.register_stop('Bus_SN1_1', 'uz1_47_uz1_48', 0.)
    roads.register_stop('Bus_SN1_2', 'uz2_0_uz2_1', 0.)
    roads.register_stop('Bus_SN1_3', 'uz2_2_uz2_3', 0.)
    roads.register_stop('Bus_SN1_4', 'uz2_4_uz2_5', 0.)
    roads.register_stop('Bus_SN1_5', 'uz2_6_uz2_7', 0.)
    roads.register_stop('Bus_SN1_6', 'uz2_8_uz2_9', 0.)
    roads.register_stop('Bus_SN1_7', 'uz2_10_uz2_11', 0.)
    roads.register_stop('Bus_SN1_8', 'uz2_12_uz1_55', 0.)
    roads.register_stop('Bus_SN1_9', 'uz1_57_uz1_42', 0.)
    roads.register_stop('Bus_SN1_10', 'uz1_44_uz0_92', 0.)
    # Bus South-North 2
    roads.register_stop('Bus_SN2_0', 'uz2_26_uz2_27', 0.)
    roads.register_stop('Bus_SN2_1', 'uz2_28_uz2_29', 0.)
    roads.register_stop('Bus_SN2_2', 'uz2_30_uz2_31', 0.)
    roads.register_stop('Bus_SN2_3', 'uz2_32_uz2_33', 0.)
    roads.register_stop('Bus_SN2_4', 'uz2_34_uz2_35', 0.)
    roads.register_stop('Bus_SN2_5', 'uz2_36_uz2_37', 0.)
    roads.register_stop('Bus_SN2_6', 'uz2_38_uz1_86', 0.)
    # Bus South-North 3
    roads.register_stop('Bus_SN3_0', 'uz1_60_uz1_61', 0.)
    roads.register_stop('Bus_SN3_1', 'uz1_77_uz1_78', 0.)
    roads.register_stop('Bus_SN3_2', 'uz2_52_uz2_53', 0.)
    roads.register_stop('Bus_SN3_3', 'uz2_54_uz2_55', 0.)
    roads.register_stop('Bus_SN3_4', 'uz2_56_uz2_57', 0.)
    roads.register_stop('Bus_SN3_5', 'uz2_58_uz2_59', 0.)
    roads.register_stop('Bus_SN3_6', 'uz2_60_uz2_61', 0.)
    roads.register_stop('Bus_SN3_7', 'uz2_62_uz2_63', 0.)
    roads.register_stop('Bus_SN3_8', 'uz2_64_uz2_51', 0.)
    roads.register_stop('Bus_SN3_9', 'uz1_87_uz1_72', 0.)
    roads.register_stop('Bus_SN3_10', 'uz1_74_uz0_108', 0.)
    # Bus South-North 4
    roads.register_stop('Bus_SN4_0', 'uz1_150_uz1_151', 0.)
    roads.register_stop('Bus_SN4_1', 'uz1_137_uz1_138', 0.)
    roads.register_stop('Bus_SN4_2', 'uz2_104_uz2_105', 0.)
    roads.register_stop('Bus_SN4_3', 'uz2_106_uz2_107', 0.)
    roads.register_stop('Bus_SN4_4', 'uz2_108_uz2_109', 0.)
    roads.register_stop('Bus_SN4_5', 'uz2_110_uz2_111', 0.)
    roads.register_stop('Bus_SN4_6', 'uz2_112_uz2_113', 0.)
    roads.register_stop('Bus_SN4_7', 'uz2_114_uz2_115', 0.)
    roads.register_stop('Bus_SN4_8', 'uz2_116_uz2_129', 0.)
    roads.register_stop('Bus_SN4_9', 'uz1_147_uz1_162', 0.)
    roads.register_stop('Bus_SN4_10', 'uz1_164_uz0_156', 0.)
    # Bus South-North 5
    roads.register_stop('Bus_SN5_0', 'uz2_130_uz2_131', 0.)
    roads.register_stop('Bus_SN5_1', 'uz2_132_uz2_133', 0.)
    roads.register_stop('Bus_SN5_2', 'uz2_134_uz2_135', 0.)
    roads.register_stop('Bus_SN5_3', 'uz2_136_uz2_137', 0.)
    roads.register_stop('Bus_SN5_4', 'uz2_138_uz2_139', 0.)
    roads.register_stop('Bus_SN5_5', 'uz2_140_uz2_141', 0.)
    roads.register_stop('Bus_SN5_6', 'uz2_142_uz1_146', 0.)
    # Bus South-North 6
    roads.register_stop('Bus_SN6_0', 'uz1_180_uz1_181', 0.)
    roads.register_stop('Bus_SN6_1', 'uz1_167_uz1_168', 0.)
    roads.register_stop('Bus_SN6_2', 'uz2_156_uz2_157', 0.)
    roads.register_stop('Bus_SN6_3', 'uz2_158_uz2_159', 0.)
    roads.register_stop('Bus_SN6_4', 'uz2_160_uz2_161', 0.)
    roads.register_stop('Bus_SN6_5', 'uz2_162_uz2_163', 0.)
    roads.register_stop('Bus_SN6_6', 'uz2_164_uz2_165', 0.)
    roads.register_stop('Bus_SN6_7', 'uz2_166_uz2_167', 0.)
    roads.register_stop('Bus_SN6_8', 'uz2_168_uz1_175', 0.)
    roads.register_stop('Bus_SN6_9', 'uz1_177_uz1_192', 0.)
    roads.register_stop('Bus_SN6_10', 'uz1_194_uz0_172', 0.)
    ## West-East
    # Bus West-East 1
    roads.register_stop('Bus_WE1_0', 'uz1_12_uz1_11', 0.)
    roads.register_stop('Bus_WE1_1', 'uz1_41_uz1_40', 0.)
    roads.register_stop('Bus_WE1_2', 'uz2_12_uz2_25', 0.)
    roads.register_stop('Bus_WE1_3', 'uz2_38_uz2_51', 0.)
    roads.register_stop('Bus_WE1_4', 'uz2_64_uz2_77', 0.)
    roads.register_stop('Bus_WE1_5', 'uz2_90_uz2_103', 0.)
    roads.register_stop('Bus_WE1_6', 'uz2_116_uz2_129', 0.)
    roads.register_stop('Bus_WE1_7', 'uz2_142_uz2_155', 0.)
    roads.register_stop('Bus_WE1_8', 'uz2_168_uz1_175', 0.)
    roads.register_stop('Bus_WE1_9', 'uz1_191_uz1_206', 0.)
    roads.register_stop('Bus_WE1_10', 'uz1_222_uz0_202', 0.)
    # Bus West-East 2
    roads.register_stop('Bus_WE2_0', 'uz2_10_uz2_23', 0.)
    roads.register_stop('Bus_WE2_1', 'uz2_36_uz2_49', 0.)
    roads.register_stop('Bus_WE2_2', 'uz2_62_uz2_75', 0.)
    roads.register_stop('Bus_WE2_3', 'uz2_88_uz2_101', 0.)
    roads.register_stop('Bus_WE2_4', 'uz2_114_uz2_127', 0.)
    roads.register_stop('Bus_WE2_5', 'uz2_140_uz2_153', 0.)
    roads.register_stop('Bus_WE2_6', 'uz2_166_uz1_174', 0.)
    # Bus West-East 3
    roads.register_stop('Bus_WE3_0', 'uz1_10_uz1_9', 0.)
    roads.register_stop('Bus_WE3_1', 'uz1_39_uz1_38', 0.)
    roads.register_stop('Bus_WE3_2', 'uz2_8_uz2_21', 0.)
    roads.register_stop('Bus_WE3_3', 'uz2_34_uz2_47', 0.)
    roads.register_stop('Bus_WE3_4', 'uz2_60_uz2_73', 0.)
    roads.register_stop('Bus_WE3_5', 'uz2_86_uz2_99', 0.)
    roads.register_stop('Bus_WE3_6', 'uz2_112_uz2_125', 0.)
    roads.register_stop('Bus_WE3_7', 'uz2_138_uz2_151', 0.)
    roads.register_stop('Bus_WE3_8', 'uz2_164_uz1_173', 0.)
    roads.register_stop('Bus_WE3_9', 'uz1_189_uz1_204', 0.)
    roads.register_stop('Bus_WE3_10', 'uz1_220_uz0_201', 0.)
    # Bus West-East 4
    roads.register_stop('Bus_WE4_0', 'uz1_4_uz1_5', 0.)
    roads.register_stop('Bus_WE4_1', 'uz1_35_uz1_36', 0.)
    roads.register_stop('Bus_WE4_2', 'uz2_4_uz2_17', 0.)
    roads.register_stop('Bus_WE4_3', 'uz2_30_uz2_43', 0.)
    roads.register_stop('Bus_WE4_4', 'uz2_56_uz2_69', 0.)
    roads.register_stop('Bus_WE4_5', 'uz2_82_uz2_95', 0.)
    roads.register_stop('Bus_WE4_6', 'uz2_108_uz2_121', 0.)
    roads.register_stop('Bus_WE4_7', 'uz2_134_uz2_147', 0.)
    roads.register_stop('Bus_WE4_8', 'uz2_160_uz1_171', 0.)
    roads.register_stop('Bus_WE4_9', 'uz1_185_uz1_200', 0.)
    roads.register_stop('Bus_WE4_10', 'uz1_214_uz0_198', 0.)
    # Bus West-East 5
    roads.register_stop('Bus_WE5_0', 'uz2_2_uz2_15', 0.)
    roads.register_stop('Bus_WE5_1', 'uz2_28_uz2_41', 0.)
    roads.register_stop('Bus_WE5_2', 'uz2_54_uz2_67', 0.)
    roads.register_stop('Bus_WE5_3', 'uz2_80_uz2_93', 0.)
    roads.register_stop('Bus_WE5_4', 'uz2_106_uz2_119', 0.)
    roads.register_stop('Bus_WE5_5', 'uz2_132_uz2_145', 0.)
    roads.register_stop('Bus_WE5_6', 'uz2_158_uz1_170', 0.)
    # Bus West-East 6
    roads.register_stop('Bus_WE6_0', 'uz1_2_uz1_3', 0.)
    roads.register_stop('Bus_WE6_1', 'uz1_33_uz1_34', 0.)
    roads.register_stop('Bus_WE6_2', 'uz2_0_uz2_13', 0.)
    roads.register_stop('Bus_WE6_3', 'uz2_26_uz2_39', 0.)
    roads.register_stop('Bus_WE6_4', 'uz2_52_uz2_65', 0.)
    roads.register_stop('Bus_WE6_5', 'uz2_78_uz2_91', 0.)
    roads.register_stop('Bus_WE6_6', 'uz2_104_uz2_117', 0.)
    roads.register_stop('Bus_WE6_7', 'uz2_130_uz2_143', 0.)
    roads.register_stop('Bus_WE6_8', 'uz2_156_uz1_169', 0.)
    roads.register_stop('Bus_WE6_9', 'uz1_183_uz1_198', 0.)
    roads.register_stop('Bus_WE6_10', 'uz1_212_uz0_197', 0.)
    ## East-West
    # Bus East-West 1
    roads.register_stop('Bus_EW1_0', 'uz1_222_uz1_221', 0.)
    roads.register_stop('Bus_EW1_1', 'uz1_191_uz1_190', 0.)
    roads.register_stop('Bus_EW1_2', 'uz2_168_uz2_155', 0.)
    roads.register_stop('Bus_EW1_3', 'uz2_142_uz2_129', 0.)
    roads.register_stop('Bus_EW1_4', 'uz2_116_uz2_103', 0.)
    roads.register_stop('Bus_EW1_5', 'uz2_90_uz2_77', 0.)
    roads.register_stop('Bus_EW1_6', 'uz2_64_uz2_51', 0.)
    roads.register_stop('Bus_EW1_7', 'uz2_38_uz2_25', 0.)
    roads.register_stop('Bus_EW1_8', 'uz2_12_uz1_55', 0.)
    roads.register_stop('Bus_EW1_9', 'uz1_41_uz1_26', 0.)
    roads.register_stop('Bus_EW1_10', 'uz1_12_uz0_58', 0.)
    # Bus East-West 2
    roads.register_stop('Bus_EW2_0', 'uz2_166_uz2_153', 0.)
    roads.register_stop('Bus_EW2_1', 'uz2_140_uz2_127', 0.)
    roads.register_stop('Bus_EW2_2', 'uz2_114_uz2_101', 0.)
    roads.register_stop('Bus_EW2_3', 'uz2_88_uz2_75', 0.)
    roads.register_stop('Bus_EW2_4', 'uz2_62_uz2_49', 0.)
    roads.register_stop('Bus_EW2_5', 'uz2_36_uz2_23', 0.)
    roads.register_stop('Bus_EW2_6', 'uz2_10_uz1_54', 0.)
    # Bus East-West 3
    roads.register_stop('Bus_EW3_0', 'uz1_220_uz1_219', 0.)
    roads.register_stop('Bus_EW3_1', 'uz1_189_uz1_188', 0.)
    roads.register_stop('Bus_EW3_2', 'uz2_164_uz2_151', 0.)
    roads.register_stop('Bus_EW3_3', 'uz2_138_uz2_125', 0.)
    roads.register_stop('Bus_EW3_4', 'uz2_112_uz2_99', 0.)
    roads.register_stop('Bus_EW3_5', 'uz2_86_uz2_73', 0.)
    roads.register_stop('Bus_EW3_6', 'uz2_60_uz2_47', 0.)
    roads.register_stop('Bus_EW3_7', 'uz2_34_uz2_21', 0.)
    roads.register_stop('Bus_EW3_8', 'uz2_8_uz1_53', 0.)
    roads.register_stop('Bus_EW3_9', 'uz1_39_uz1_24', 0.)
    roads.register_stop('Bus_EW3_10', 'uz1_10_uz0_57', 0.)
    # Bus East-West 4
    roads.register_stop('Bus_EW4_0', 'uz1_214_uz1_215', 0.)
    roads.register_stop('Bus_EW4_1', 'uz1_185_uz1_186', 0.)
    roads.register_stop('Bus_EW4_2', 'uz2_160_uz2_147', 0.)
    roads.register_stop('Bus_EW4_3', 'uz2_134_uz2_121', 0.)
    roads.register_stop('Bus_EW4_4', 'uz2_108_uz2_95', 0.)
    roads.register_stop('Bus_EW4_5', 'uz2_82_uz2_69', 0.)
    roads.register_stop('Bus_EW4_6', 'uz2_56_uz2_43', 0.)
    roads.register_stop('Bus_EW4_7', 'uz2_30_uz2_17', 0.)
    roads.register_stop('Bus_EW4_8', 'uz2_4_uz1_51', 0.)
    roads.register_stop('Bus_EW4_9', 'uz1_35_uz1_20', 0.)
    roads.register_stop('Bus_EW4_10', 'uz1_4_uz0_54', 0.)
    # Bus East-West 5
    roads.register_stop('Bus_EW5_0', 'uz2_158_uz2_145', 0.)
    roads.register_stop('Bus_EW5_1', 'uz2_132_uz2_119', 0.)
    roads.register_stop('Bus_EW5_2', 'uz2_106_uz2_93', 0.)
    roads.register_stop('Bus_EW5_3', 'uz2_80_uz2_67', 0.)
    roads.register_stop('Bus_EW5_4', 'uz2_54_uz2_41', 0.)
    roads.register_stop('Bus_EW5_5', 'uz2_28_uz2_15', 0.)
    roads.register_stop('Bus_EW5_6', 'uz2_2_uz1_50', 0.)
    # Bus East-West 6
    roads.register_stop('Bus_EW6_0', 'uz1_212_uz1_213', 0.)
    roads.register_stop('Bus_EW6_1', 'uz1_183_uz1_184', 0.)
    roads.register_stop('Bus_EW6_2', 'uz2_156_uz2_143', 0.)
    roads.register_stop('Bus_EW6_3', 'uz2_130_uz2_117', 0.)
    roads.register_stop('Bus_EW6_4', 'uz2_104_uz2_91', 0.)
    roads.register_stop('Bus_EW6_5', 'uz2_78_uz2_65', 0.)
    roads.register_stop('Bus_EW6_6', 'uz2_52_uz2_39', 0.)
    roads.register_stop('Bus_EW6_7', 'uz2_26_uz2_13', 0.)
    roads.register_stop('Bus_EW6_8', 'uz2_0_uz1_49', 0.)
    roads.register_stop('Bus_EW6_9', 'uz1_33_uz1_18', 0.)
    roads.register_stop('Bus_EW6_10', 'uz1_2_uz0_53', 0.)

    ### Feeder bus
    ## North
    # Feeder bus North 1
    roads.register_stop('Bus_feederN1_0', 'uz0_124_uz1_104', 0.)
    roads.register_stop('Bus_feederN1_1', 'uz1_104_uz1_103', 0.)
    roads.register_stop('Bus_feederN1_2', 'uz1_117_uz1_132', 0.)
    roads.register_stop('Bus_feederN1_3', 'uz1_134_uz0_140', 0.)
    roads.register_stop('Bus_feederN1_4', 'uz0_140_uz0_124b', 0.)
    # Feeder bus North 2
    roads.register_stop('Bus_feederN2_0', 'uz0_140_uz1_134', 0.)
    roads.register_stop('Bus_feederN2_1', 'uz1_134_uz1_133', 0.)
    roads.register_stop('Bus_feederN2_2', 'uz1_117_uz1_102', 0.)
    roads.register_stop('Bus_feederN2_3', 'uz1_104_uz0_124', 0.)
    roads.register_stop('Bus_feederN2_4', 'uz0_124_uz0_124b', 0.)
    # Feeder bus North West->East
    roads.register_stop('Bus_feederNWE_0', 'uz0_46_uz0_62', 0.)
    roads.register_stop('Bus_feederNWE_1', 'uz0_78_uz0_94', 0.)
    roads.register_stop('Bus_feederNWE_2', 'uz0_110_uz0_126', 0.)
    roads.register_stop('Bus_feederNWE_3', 'uz0_126b_uz0_142', 0.)
    roads.register_stop('Bus_feederNWE_4', 'uz0_158_uz0_174', 0.)
    roads.register_stop('Bus_feederNWE_5', 'uz0_190_uz0_206', 0.)
    roads.register_stop('Bus_feederNWE_6', 'uz0_222_uz0_238', 0.)
    # Feeder bus North East->West
    roads.register_stop('Bus_feederNEW_0', 'uz0_222_uz0_206', 0.)
    roads.register_stop('Bus_feederNEW_1', 'uz0_190_uz0_174', 0.)
    roads.register_stop('Bus_feederNEW_2', 'uz0_158_uz0_142', 0.)
    roads.register_stop('Bus_feederNEW_3', 'uz0_126b_uz0_126', 0.)
    roads.register_stop('Bus_feederNEW_4', 'uz0_110_uz0_94', 0.)
    roads.register_stop('Bus_feederNEW_5', 'uz0_78_uz0_62', 0.)
    roads.register_stop('Bus_feederNEW_6', 'uz0_46_uz0_30', 0.)
    ## South
    # Feeder bus South 1
    roads.register_stop('Bus_feederS1_0', 'uz0_131_uz1_120', 0.)
    roads.register_stop('Bus_feederS1_1', 'uz1_120_uz1_121', 0.)
    roads.register_stop('Bus_feederS1_2', 'uz1_107_uz1_92', 0.)
    roads.register_stop('Bus_feederS1_3', 'uz1_90_uz0_115', 0.)
    roads.register_stop('Bus_feederS1_4', 'uz0_115_uz0_115b', 0.)
    # Feeder bus South 2
    roads.register_stop('Bus_feederS2_0', 'uz0_115_uz1_90', 0.)
    roads.register_stop('Bus_feederS2_1', 'uz1_90_uz1_91', 0.)
    roads.register_stop('Bus_feederS2_2', 'uz1_107_uz1_122', 0.)
    roads.register_stop('Bus_feederS2_3', 'uz1_120_uz0_131', 0.)
    roads.register_stop('Bus_feederS2_4', 'uz0_131_uz0_115b', 0.)
    # Feeder bus South West->East
    roads.register_stop('Bus_feederSWE_0', 'uz0_33_uz0_49', 0.)
    roads.register_stop('Bus_feederSWE_1', 'uz0_65_uz0_81', 0.)
    roads.register_stop('Bus_feederSWE_2', 'uz0_97_uz0_113', 0.)
    roads.register_stop('Bus_feederSWE_3', 'uz0_113b_uz0_129', 0.)
    roads.register_stop('Bus_feederSWE_4', 'uz0_145_uz0_161', 0.)
    roads.register_stop('Bus_feederSWE_5', 'uz0_177_uz0_193', 0.)
    roads.register_stop('Bus_feederSWE_6', 'uz0_209_uz0_225', 0.)
    # Feeder bus South East->West
    roads.register_stop('Bus_feederSEW_0', 'uz0_209_uz0_193', 0.)
    roads.register_stop('Bus_feederSEW_1', 'uz0_177_uz0_161', 0.)
    roads.register_stop('Bus_feederSEW_2', 'uz0_145_uz0_129', 0.)
    roads.register_stop('Bus_feederSEW_3', 'uz0_113b_uz0_113', 0.)
    roads.register_stop('Bus_feederSEW_4', 'uz0_97_uz0_81', 0.)
    roads.register_stop('Bus_feederSEW_5', 'uz0_65_uz0_49', 0.)
    roads.register_stop('Bus_feederSEW_6', 'uz0_33_uz0_17', 0.)
    ## West
    # Feeder bus West 1
    roads.register_stop('Bus_feederW1_0', 'uz0_55_uz1_6', 0.)
    roads.register_stop('Bus_feederW1_1', 'uz1_6_uz1_21', 0.)
    roads.register_stop('Bus_feederW1_2', 'uz1_37_uz1_38', 0.)
    roads.register_stop('Bus_feederW1_3', 'uz1_8_uz0_56', 0.)
    roads.register_stop('Bus_feederW1_4', 'uz0_56_uz0_55b', 0.)
    # Feeder bus West 2
    roads.register_stop('Bus_feederW2_0', 'uz0_56_uz1_8', 0.)
    roads.register_stop('Bus_feederW2_1', 'uz1_8_uz1_23', 0.)
    roads.register_stop('Bus_feederW2_2', 'uz1_37_uz1_36', 0.)
    roads.register_stop('Bus_feederW2_3', 'uz1_6_uz0_55', 0.)
    roads.register_stop('Bus_feederW2_4', 'uz0_55_uz0_55b', 0.)
    # Feeder bus West North->South
    roads.register_stop('Bus_feederWNS_0', 'uz0_29_uz0_28', 0.)
    roads.register_stop('Bus_feederWNS_1', 'uz0_27_uz0_26', 0.)
    roads.register_stop('Bus_feederWNS_2', 'uz0_25_uz0_24', 0.)
    roads.register_stop('Bus_feederWNS_3', 'uz0_23b_uz0_23', 0.)
    roads.register_stop('Bus_feederWNS_4', 'uz0_22_uz0_21', 0.)
    roads.register_stop('Bus_feederWNS_5', 'uz0_20_uz0_19', 0.)
    roads.register_stop('Bus_feederWNS_6', 'uz0_18_uz0_17', 0.)
    # Feeder bus West South->North
    roads.register_stop('Bus_feederWSN_0', 'uz0_18_uz0_19', 0.)
    roads.register_stop('Bus_feederWSN_1', 'uz0_20_uz0_21', 0.)
    roads.register_stop('Bus_feederWSN_2', 'uz0_22_uz0_23', 0.)
    roads.register_stop('Bus_feederWSN_3', 'uz0_23b_uz0_24', 0.)
    roads.register_stop('Bus_feederWSN_4', 'uz0_25_uz0_26', 0.)
    roads.register_stop('Bus_feederWSN_5', 'uz0_27_uz0_28', 0.)
    roads.register_stop('Bus_feederWSN_6', 'uz0_29_uz0_30', 0.)
    ## East
    # Feeder bus East 1
    roads.register_stop('Bus_feederE1_0', 'uz0_200_uz1_218', 0.)
    roads.register_stop('Bus_feederE1_1', 'uz1_218_uz1_203', 0.)
    roads.register_stop('Bus_feederE1_2', 'uz1_187_uz1_186', 0.)
    roads.register_stop('Bus_feederE1_3', 'uz1_216_uz0_199', 0.)
    roads.register_stop('Bus_feederE1_4', 'uz0_199_uz0_199b', 0.)
    # Feeder bus East 2
    roads.register_stop('Bus_feederE2_0', 'uz0_199_uz1_216', 0.)
    roads.register_stop('Bus_feederE2_1', 'uz1_216_uz1_201', 0.)
    roads.register_stop('Bus_feederE2_2', 'uz1_187_uz1_188', 0.)
    roads.register_stop('Bus_feederE2_3', 'uz1_218_uz0_200', 0.)
    roads.register_stop('Bus_feederE2_4', 'uz0_200_uz0_199b', 0.)
    # Feeder bus East North->South
    roads.register_stop('Bus_feederENS_0', 'uz0_237_uz0_236', 0.)
    roads.register_stop('Bus_feederENS_1', 'uz0_235_uz0_234', 0.)
    roads.register_stop('Bus_feederENS_2', 'uz0_233_uz0_232', 0.)
    roads.register_stop('Bus_feederENS_3', 'uz0_231b_uz0_231', 0.)
    roads.register_stop('Bus_feederENS_4', 'uz0_230_uz0_229', 0.)
    roads.register_stop('Bus_feederENS_5', 'uz0_228_uz0_227', 0.)
    roads.register_stop('Bus_feederENS_6', 'uz0_226_uz0_225', 0.)
    # Feeder bus East South->North
    roads.register_stop('Bus_feederESN_0', 'uz0_226_uz0_227', 0.)
    roads.register_stop('Bus_feederESN_1', 'uz0_228_uz0_229', 0.)
    roads.register_stop('Bus_feederESN_2', 'uz0_230_uz0_231', 0.)
    roads.register_stop('Bus_feederESN_3', 'uz0_231b_uz0_232', 0.)
    roads.register_stop('Bus_feederESN_4', 'uz0_233_uz0_234', 0.)
    roads.register_stop('Bus_feederESN_5', 'uz0_235_uz0_236', 0.)
    roads.register_stop('Bus_feederESN_6', 'uz0_237_uz0_238', 0.)
    ### Metro
    ## North->South
    roads.register_stop('Metro_NS_0', 'uz1_117_uz1_116', 0.)
    roads.register_stop('Metro_NS_1', 'uz2_90_uz2_89', 0.)
    roads.register_stop('Metro_NS_2', 'uz2_88_uz2_87', 0.)
    roads.register_stop('Metro_NS_3', 'uz2_86_uz2_85', 0.)
    roads.register_stop('Metro_NS_4', 'uz2_84_uz2_83', 0.)
    roads.register_stop('Metro_NS_5', 'uz2_82_uz2_81', 0.)
    roads.register_stop('Metro_NS_6', 'uz2_80_uz2_79', 0.)
    roads.register_stop('Metro_NS_7', 'uz2_78_uz1_108', 0.)
    roads.register_stop('Metro_NS_8', 'uz1_107_uz1_106', 0.)
    ## South->North
    roads.register_stop('Metro_SN_0', 'uz1_107_uz1_108', 0.)
    roads.register_stop('Metro_SN_1', 'uz2_78_uz2_79', 0.)
    roads.register_stop('Metro_SN_2', 'uz2_80_uz2_81', 0.)
    roads.register_stop('Metro_SN_3', 'uz2_82_uz2_83', 0.)
    roads.register_stop('Metro_SN_4', 'uz2_84_uz2_85', 0.)
    roads.register_stop('Metro_SN_5', 'uz2_86_uz2_87', 0.)
    roads.register_stop('Metro_SN_6', 'uz2_88_uz2_89', 0.)
    roads.register_stop('Metro_SN_7', 'uz2_90_uz1_116', 0.)
    roads.register_stop('Metro_SN_8', 'uz1_117_uz1_118', 0.)
    ## West->East
    roads.register_stop('Metro_WE_0', 'uz1_37_uz1_52', 0.)
    roads.register_stop('Metro_WE_1', 'uz2_6_uz2_19', 0.)
    roads.register_stop('Metro_WE_2', 'uz2_32_uz2_45', 0.)
    roads.register_stop('Metro_WE_3', 'uz2_58_uz2_71', 0.)
    roads.register_stop('Metro_WE_4', 'uz2_84_uz2_97', 0.)
    roads.register_stop('Metro_WE_5', 'uz2_110_uz2_123', 0.)
    roads.register_stop('Metro_WE_6', 'uz2_136_uz2_149', 0.)
    roads.register_stop('Metro_WE_7', 'uz2_162_uz1_172', 0.)
    roads.register_stop('Metro_WE_8', 'uz1_187_uz1_202', 0.)
    ## East->West
    roads.register_stop('Metro_EW_0', 'uz1_187_uz1_172', 0.)
    roads.register_stop('Metro_EW_1', 'uz2_162_uz2_149', 0.)
    roads.register_stop('Metro_EW_2', 'uz2_136_uz2_123', 0.)
    roads.register_stop('Metro_EW_3', 'uz2_110_uz2_97', 0.)
    roads.register_stop('Metro_EW_4', 'uz2_84_uz2_71', 0.)
    roads.register_stop('Metro_EW_5', 'uz2_58_uz2_45', 0.)
    roads.register_stop('Metro_EW_6', 'uz2_32_uz2_19', 0.)
    roads.register_stop('Metro_EW_7', 'uz2_6_uz1_52', 0.)
    roads.register_stop('Metro_EW_8', 'uz1_37_uz1_22', 0.)

    ### Train
    # North -> South
    roads.register_stop('Train_NS_0', 'Rail_1_Rail_2', 0.)
    roads.register_stop('Train_NS_1', 'Rail_2_Rail_3', 0.)
    roads.register_stop('Train_NS_2', 'Rail_3_Rail_4', 0.)
    roads.register_stop('Train_NS_3', 'Rail_4_Rail_5', 0.)
    roads.register_stop('Train_NS_4', 'Rail_5_Rail_6', 0.)
    roads.register_stop('Train_NS_5', 'Rail_6_Rail_7', 0.)
    roads.register_stop('Train_NS_6', 'Rail_6_Rail_7', 1.)

    # South -> North
    roads.register_stop('Train_SN_0', 'Rail_7_Rail_6', 0.)
    roads.register_stop('Train_SN_1', 'Rail_6_Rail_5', 0.)
    roads.register_stop('Train_SN_2', 'Rail_5_Rail_4', 0.)
    roads.register_stop('Train_SN_3', 'Rail_4_Rail_3', 0.)
    roads.register_stop('Train_SN_4', 'Rail_3_Rail_2', 0.)
    roads.register_stop('Train_SN_5', 'Rail_2_Rail_1', 0.)
    roads.register_stop('Train_SN_6', 'Rail_2_Rail_1', 1.)

    # West -> East
    roads.register_stop('Train_WE_0', 'Rail_8_Rail_9', 0.)
    roads.register_stop('Train_WE_1', 'Rail_9_Rail_10', 0.)
    roads.register_stop('Train_WE_2', 'Rail_10_Rail_4', 0.)
    roads.register_stop('Train_WE_3', 'Rail_4_Rail_11', 0.)
    roads.register_stop('Train_WE_4', 'Rail_11_Rail_12', 0.)
    roads.register_stop('Train_WE_5', 'Rail_12_Rail_13', 0.)
    roads.register_stop('Train_WE_6', 'Rail_12_Rail_13', 1.)

    # East -> West
    roads.register_stop('Train_EW_0', 'Rail_13_Rail_12', 0.)
    roads.register_stop('Train_EW_1', 'Rail_12_Rail_11', 0.)
    roads.register_stop('Train_EW_2', 'Rail_11_Rail_4', 0.)
    roads.register_stop('Train_EW_3', 'Rail_4_Rail_10', 0.)
    roads.register_stop('Train_EW_4', 'Rail_10_Rail_9', 0.)
    roads.register_stop('Train_EW_5', 'Rail_9_Rail_8', 0.)
    roads.register_stop('Train_EW_6', 'Rail_9_Rail_8', 1.)


def generate_daganzo_hybrid_transit_network_lines(bus_layer, metro_layer, train_layer,
    bus_freq, feederbus_freq, metro_freq, train_freq):
    #### Lines creation
    ### Bus
    ## North->South
    bus_layer.create_line('Bus_NS1',
                        ['Bus_NS1_0', 'Bus_NS1_1', 'Bus_NS1_2', 'Bus_NS1_3', 'Bus_NS1_4',
                            'Bus_NS1_5', 'Bus_NS1_6', 'Bus_NS1_7', 'Bus_NS1_8',
                            'Bus_NS1_9', 'Bus_NS1_10'],
                        [['uz1_44_uz1_43', 'uz1_43_uz1_42', 'uz1_42_uz1_57', 'uz1_57_uz1_56'],
                        ['uz1_57_uz1_56', 'uz1_56_uz1_55', 'uz1_55_uz2_12', 'uz2_12_uz2_11'],
                        ['uz2_12_uz2_11', 'uz2_11_uz2_10', 'uz2_10_uz2_9'],
                        ['uz2_10_uz2_9', 'uz2_9_uz2_8', 'uz2_8_uz2_7'],
                        ['uz2_8_uz2_7', 'uz2_7_uz2_6', 'uz2_6_uz2_5'],
                        ['uz2_6_uz2_5', 'uz2_5_uz2_4', 'uz2_4_uz2_3'],
                        ['uz2_4_uz2_3', 'uz2_3_uz2_2', 'uz2_2_uz2_1'],
                        ['uz2_2_uz2_1', 'uz2_1_uz2_0', 'uz2_0_uz1_49'],
                        ['uz2_0_uz1_49', 'uz1_49_uz1_48', 'uz1_48_uz1_47', 'uz1_47_uz1_32'],
                        ['uz1_47_uz1_32', 'uz1_32_uz1_31', 'uz1_31_uz1_30', 'uz1_30_uz0_83']
                        ],
                        TimeTable.create_table_freq('07:00:00', '12:00:00', Dt(minutes=bus_freq)))
    bus_layer.create_line('Bus_NS2',
                        ['Bus_NS2_0', 'Bus_NS2_1', 'Bus_NS2_2', 'Bus_NS2_3', 'Bus_NS2_4',
                            'Bus_NS2_5', 'Bus_NS2_6'],
                        [['uz2_38_uz2_37', 'uz2_37_uz2_36', 'uz2_36_uz2_35'],
                        ['uz2_36_uz2_35', 'uz2_35_uz2_34', 'uz2_34_uz2_33'],
                        ['uz2_34_uz2_33', 'uz2_33_uz2_32', 'uz2_32_uz2_31'],
                        ['uz2_32_uz2_31', 'uz2_31_uz2_30', 'uz2_30_uz2_29'],
                        ['uz2_30_uz2_29', 'uz2_29_uz2_28', 'uz2_28_uz2_27'],
                        ['uz2_28_uz2_27', 'uz2_27_uz2_26', 'uz2_26_uz1_78']
                        ],
                        TimeTable.create_table_freq('07:00:00', '12:00:00', Dt(minutes=bus_freq)))
    bus_layer.create_line('Bus_NS3',
                        ['Bus_NS3_0', 'Bus_NS3_1', 'Bus_NS3_2', 'Bus_NS3_3', 'Bus_NS3_4',
                            'Bus_NS3_5', 'Bus_NS3_6', 'Bus_NS3_7', 'Bus_NS3_8',
                            'Bus_NS3_9', 'Bus_NS3_10'],
                        [['uz1_74_uz1_73', 'uz1_73_uz1_72', 'uz1_72_uz1_87', 'uz1_87_uz1_86'],
                        ['uz1_87_uz1_86', 'uz1_86_uz2_38', 'uz2_38_uz2_51', 'uz2_51_uz2_64', 'uz2_64_uz2_63'],
                        ['uz2_64_uz2_63', 'uz2_63_uz2_62', 'uz2_62_uz2_61'],
                        ['uz2_62_uz2_61', 'uz2_61_uz2_60', 'uz2_60_uz2_59'],
                        ['uz2_60_uz2_59', 'uz2_59_uz2_58', 'uz2_58_uz2_57'],
                        ['uz2_58_uz2_57', 'uz2_57_uz2_56', 'uz2_56_uz2_55'],
                        ['uz2_56_uz2_55', 'uz2_55_uz2_54', 'uz2_54_uz2_53'],
                        ['uz2_54_uz2_53', 'uz2_53_uz2_52', 'uz2_52_uz2_39'],
                        ['uz2_52_uz2_39', 'uz2_39_uz2_26', 'uz2_26_uz1_78', 'uz1_78_uz1_77', 'uz1_77_uz1_62'],
                        ['uz1_77_uz1_62', 'uz1_62_uz1_61', 'uz1_61_uz1_60', 'uz1_60_uz0_99'],
                        ],
                        TimeTable.create_table_freq('07:00:00', '12:00:00', Dt(minutes=bus_freq)))
    bus_layer.create_line('Bus_NS4',
                        ['Bus_NS4_0', 'Bus_NS4_1', 'Bus_NS4_2', 'Bus_NS4_3', 'Bus_NS4_4',
                            'Bus_NS4_5', 'Bus_NS4_6', 'Bus_NS4_7', 'Bus_NS4_8',
                            'Bus_NS4_9', 'Bus_NS4_10'],
                        [['uz1_164_uz1_163', 'uz1_163_uz1_162', 'uz1_162_uz1_147', 'uz1_147_uz1_146'],
                        ['uz1_147_uz1_146', 'uz1_146_uz2_142', 'uz2_142_uz2_129', 'uz2_129_uz2_116', 'uz2_116_uz2_115'],
                        ['uz2_116_uz2_115', 'uz2_115_uz2_114', 'uz2_114_uz2_113'],
                        ['uz2_114_uz2_113', 'uz2_113_uz2_112', 'uz2_112_uz2_111'],
                        ['uz2_112_uz2_111', 'uz2_111_uz2_110', 'uz2_110_uz2_109'],
                        ['uz2_110_uz2_109', 'uz2_109_uz2_108', 'uz2_108_uz2_107'],
                        ['uz2_108_uz2_107', 'uz2_107_uz2_106', 'uz2_106_uz2_105'],
                        ['uz2_106_uz2_105', 'uz2_105_uz2_104', 'uz2_104_uz2_117'],
                        ['uz2_104_uz2_117', 'uz2_117_uz2_130', 'uz2_130_uz1_138', 'uz1_138_uz1_137', 'uz1_137_uz1_152'],
                        ['uz1_137_uz1_152', 'uz1_152_uz1_151', 'uz1_151_uz1_150', 'uz1_150_uz0_147']
                        ],
                        TimeTable.create_table_freq('07:00:00', '12:00:00', Dt(minutes=bus_freq)))
    bus_layer.create_line('Bus_NS5',
                        ['Bus_NS5_0', 'Bus_NS5_1', 'Bus_NS5_2', 'Bus_NS5_3', 'Bus_NS5_4',
                            'Bus_NS5_5', 'Bus_NS5_6'],
                        [['uz2_142_uz2_141', 'uz2_141_uz2_140', 'uz2_140_uz2_139'],
                        ['uz2_140_uz2_139', 'uz2_139_uz2_138', 'uz2_138_uz2_137'],
                        ['uz2_138_uz2_137', 'uz2_137_uz2_136', 'uz2_136_uz2_135'],
                        ['uz2_136_uz2_135', 'uz2_135_uz2_134', 'uz2_134_uz2_133'],
                        ['uz2_134_uz2_133', 'uz2_133_uz2_132', 'uz2_132_uz2_131'],
                        ['uz2_132_uz2_131', 'uz2_131_uz2_130', 'uz2_130_uz1_138']
                        ],
                        TimeTable.create_table_freq('07:00:00', '12:00:00', Dt(minutes=bus_freq)))
    bus_layer.create_line('Bus_NS6',
                        ['Bus_NS6_0', 'Bus_NS6_1', 'Bus_NS6_2', 'Bus_NS6_3', 'Bus_NS6_4',
                            'Bus_NS6_5', 'Bus_NS6_6', 'Bus_NS6_7', 'Bus_NS6_8',
                            'Bus_NS6_9', 'Bus_NS6_10'],
                        [['uz1_194_uz1_193', 'uz1_193_uz1_192', 'uz1_192_uz1_177', 'uz1_177_uz1_176'],
                        ['uz1_177_uz1_176', 'uz1_176_uz1_175', 'uz1_175_uz2_168', 'uz2_168_uz2_167'],
                        ['uz2_168_uz2_167', 'uz2_167_uz2_166', 'uz2_166_uz2_165'],
                        ['uz2_166_uz2_165', 'uz2_165_uz2_164', 'uz2_164_uz2_163'],
                        ['uz2_164_uz2_163', 'uz2_163_uz2_162', 'uz2_162_uz2_161'],
                        ['uz2_162_uz2_161', 'uz2_161_uz2_160', 'uz2_160_uz2_159'],
                        ['uz2_160_uz2_159', 'uz2_159_uz2_158', 'uz2_158_uz2_157'],
                        ['uz2_158_uz2_157', 'uz2_157_uz2_156', 'uz2_156_uz1_169'],
                        ['uz2_156_uz1_169', 'uz1_169_uz1_168', 'uz1_168_uz1_167', 'uz1_167_uz1_182'],
                        ['uz1_167_uz1_182', 'uz1_182_uz1_181', 'uz1_181_uz1_180', 'uz1_180_uz0_163']
                        ],
                        TimeTable.create_table_freq('07:00:00', '12:00:00', Dt(minutes=bus_freq)))
    ## South->North
    bus_layer.create_line('Bus_SN1',
                        ['Bus_SN1_0', 'Bus_SN1_1', 'Bus_SN1_2', 'Bus_SN1_3', 'Bus_SN1_4',
                            'Bus_SN1_5', 'Bus_SN1_6', 'Bus_SN1_7', 'Bus_SN1_8',
                            'Bus_SN1_9', 'Bus_SN1_10'],
                        [['uz1_30_uz1_31', 'uz1_31_uz1_32', 'uz1_32_uz1_47', 'uz1_47_uz1_48'],
                        ['uz1_47_uz1_48', 'uz1_48_uz1_49', 'uz1_49_uz2_0', 'uz2_0_uz2_1'],
                        ['uz2_0_uz2_1', 'uz2_1_uz2_2', 'uz2_2_uz2_3'],
                        ['uz2_2_uz2_3', 'uz2_3_uz2_4', 'uz2_4_uz2_5'],
                        ['uz2_4_uz2_5', 'uz2_5_uz2_6', 'uz2_6_uz2_7'],
                        ['uz2_6_uz2_7', 'uz2_7_uz2_8', 'uz2_8_uz2_9'],
                        ['uz2_8_uz2_9', 'uz2_9_uz2_10', 'uz2_10_uz2_11'],
                        ['uz2_10_uz2_11', 'uz2_11_uz2_12', 'uz2_12_uz1_55'],
                        ['uz2_12_uz1_55', 'uz1_55_uz1_56', 'uz1_56_uz1_57', 'uz1_57_uz1_42'],
                        ['uz1_57_uz1_42', 'uz1_42_uz1_43', 'uz1_43_uz1_44', 'uz1_44_uz0_92']
                        ],
                        TimeTable.create_table_freq('07:00:00', '12:00:00', Dt(minutes=bus_freq)))
    bus_layer.create_line('Bus_SN2',
                        ['Bus_SN2_0', 'Bus_SN2_1', 'Bus_SN2_2', 'Bus_SN2_3', 'Bus_SN2_4',
                            'Bus_SN2_5', 'Bus_SN2_6'],
                        [['uz2_26_uz2_27', 'uz2_27_uz2_28', 'uz2_28_uz2_29'],
                        ['uz2_28_uz2_29', 'uz2_29_uz2_30', 'uz2_30_uz2_31'],
                        ['uz2_30_uz2_31', 'uz2_31_uz2_32', 'uz2_32_uz2_33'],
                        ['uz2_32_uz2_33', 'uz2_33_uz2_34', 'uz2_34_uz2_35'],
                        ['uz2_34_uz2_35', 'uz2_35_uz2_36', 'uz2_36_uz2_37'],
                        ['uz2_36_uz2_37', 'uz2_37_uz2_38', 'uz2_38_uz1_86']
                        ],
                        TimeTable.create_table_freq('07:00:00', '12:00:00', Dt(minutes=bus_freq)))
    bus_layer.create_line('Bus_SN3',
                        ['Bus_SN3_0', 'Bus_SN3_1', 'Bus_SN3_2', 'Bus_SN3_3', 'Bus_SN3_4',
                            'Bus_SN3_5', 'Bus_SN3_6', 'Bus_SN3_7', 'Bus_SN3_8',
                            'Bus_SN3_9', 'Bus_SN3_10'],
                        [['uz1_60_uz1_61', 'uz1_61_uz1_62', 'uz1_62_uz1_77', 'uz1_77_uz1_78'],
                        ['uz1_77_uz1_78', 'uz1_78_uz2_26', 'uz2_26_uz2_39', 'uz2_39_uz2_52', 'uz2_52_uz2_53'],
                        ['uz2_52_uz2_53', 'uz2_53_uz2_54', 'uz2_54_uz2_55'],
                        ['uz2_54_uz2_55', 'uz2_55_uz2_56', 'uz2_56_uz2_57'],
                        ['uz2_56_uz2_57', 'uz2_57_uz2_58', 'uz2_58_uz2_59'],
                        ['uz2_58_uz2_59', 'uz2_59_uz2_60', 'uz2_60_uz2_61'],
                        ['uz2_60_uz2_61', 'uz2_61_uz2_62', 'uz2_62_uz2_63'],
                        ['uz2_62_uz2_63', 'uz2_63_uz2_64', 'uz2_64_uz2_51'],
                        ['uz2_64_uz2_51', 'uz2_51_uz2_38', 'uz2_38_uz1_86', 'uz1_86_uz1_87', 'uz1_87_uz1_72'],
                        ['uz1_87_uz1_72', 'uz1_72_uz1_73', 'uz1_73_uz1_74', 'uz1_74_uz0_108']
                        ],
                        TimeTable.create_table_freq('07:00:00', '12:00:00', Dt(minutes=bus_freq)))
    bus_layer.create_line('Bus_SN4',
                        ['Bus_SN4_0', 'Bus_SN4_1', 'Bus_SN4_2', 'Bus_SN4_3', 'Bus_SN4_4',
                            'Bus_SN4_5', 'Bus_SN4_6', 'Bus_SN4_7', 'Bus_SN4_8',
                            'Bus_SN4_9', 'Bus_SN4_10'],
                        [['uz1_150_uz1_151', 'uz1_151_uz1_152', 'uz1_152_uz1_137', 'uz1_137_uz1_138'],
                        ['uz1_137_uz1_138', 'uz1_138_uz2_130', 'uz2_130_uz2_117', 'uz2_117_uz2_104', 'uz2_104_uz2_105'],
                        ['uz2_104_uz2_105', 'uz2_105_uz2_106', 'uz2_106_uz2_107'],
                        ['uz2_106_uz2_107', 'uz2_107_uz2_108', 'uz2_108_uz2_109'],
                        ['uz2_108_uz2_109', 'uz2_109_uz2_110', 'uz2_110_uz2_111'],
                        ['uz2_110_uz2_111', 'uz2_111_uz2_112', 'uz2_112_uz2_113'],
                        ['uz2_112_uz2_113', 'uz2_113_uz2_114', 'uz2_114_uz2_115'],
                        ['uz2_114_uz2_115', 'uz2_115_uz2_116', 'uz2_116_uz2_129'],
                        ['uz2_116_uz2_129', 'uz2_129_uz2_142', 'uz2_142_uz1_146', 'uz1_146_uz1_147', 'uz1_147_uz1_162'],
                        ['uz1_147_uz1_162', 'uz1_162_uz1_163', 'uz1_163_uz1_164', 'uz1_164_uz0_156']
                        ],
                        TimeTable.create_table_freq('07:00:00', '12:00:00', Dt(minutes=bus_freq)))
    bus_layer.create_line('Bus_SN5',
                        ['Bus_SN5_0', 'Bus_SN5_1', 'Bus_SN5_2', 'Bus_SN5_3', 'Bus_SN5_4',
                            'Bus_SN5_5', 'Bus_SN5_6'],
                        [['uz2_130_uz2_131', 'uz2_131_uz2_132', 'uz2_132_uz2_133'],
                        ['uz2_132_uz2_133', 'uz2_133_uz2_134', 'uz2_134_uz2_135'],
                        ['uz2_134_uz2_135', 'uz2_135_uz2_136', 'uz2_136_uz2_137'],
                        ['uz2_136_uz2_137', 'uz2_137_uz2_138', 'uz2_138_uz2_139'],
                        ['uz2_138_uz2_139', 'uz2_139_uz2_140', 'uz2_140_uz2_141'],
                        ['uz2_140_uz2_141', 'uz2_141_uz2_142', 'uz2_142_uz1_146']
                        ],
                        TimeTable.create_table_freq('07:00:00', '12:00:00', Dt(minutes=bus_freq)))
    bus_layer.create_line('Bus_SN6',
                        ['Bus_SN6_0', 'Bus_SN6_1', 'Bus_SN6_2', 'Bus_SN6_3', 'Bus_SN6_4',
                            'Bus_SN6_5', 'Bus_SN6_6', 'Bus_SN6_7', 'Bus_SN6_8',
                            'Bus_SN6_9', 'Bus_SN6_10'],
                        [['uz1_180_uz1_181', 'uz1_181_uz1_182', 'uz1_182_uz1_167', 'uz1_167_uz1_168'],
                        ['uz1_167_uz1_168', 'uz1_168_uz1_169', 'uz1_169_uz2_156', 'uz2_156_uz2_157'],
                        ['uz2_156_uz2_157', 'uz2_157_uz2_158', 'uz2_158_uz2_159'],
                        ['uz2_158_uz2_159', 'uz2_159_uz2_160', 'uz2_160_uz2_161'],
                        ['uz2_160_uz2_161', 'uz2_161_uz2_162', 'uz2_162_uz2_163'],
                        ['uz2_162_uz2_163', 'uz2_163_uz2_164', 'uz2_164_uz2_165'],
                        ['uz2_164_uz2_165', 'uz2_165_uz2_166', 'uz2_166_uz2_167'],
                        ['uz2_166_uz2_167', 'uz2_167_uz2_168', 'uz2_168_uz1_175'],
                        ['uz2_168_uz1_175', 'uz1_175_uz1_176', 'uz1_176_uz1_177', 'uz1_177_uz1_192'],
                        ['uz1_177_uz1_192', 'uz1_192_uz1_193', 'uz1_193_uz1_194', 'uz1_194_uz0_172']
                        ],
                        TimeTable.create_table_freq('07:00:00', '12:00:00', Dt(minutes=bus_freq)))
    ## West->East
    bus_layer.create_line('Bus_WE1',
                        ['Bus_WE1_0', 'Bus_WE1_1', 'Bus_WE1_2', 'Bus_WE1_3', 'Bus_WE1_4',
                            'Bus_WE1_5', 'Bus_WE1_6', 'Bus_WE1_7', 'Bus_WE1_8',
                            'Bus_WE1_9', 'Bus_WE1_10'],
                        [['uz1_12_uz1_11', 'uz1_11_uz1_26', 'uz1_26_uz1_41', 'uz1_41_uz1_40'],
                        ['uz1_41_uz1_40', 'uz1_40_uz1_55', 'uz1_55_uz2_12', 'uz2_12_uz2_25'],
                        ['uz2_12_uz2_25', 'uz2_25_uz2_38', 'uz2_38_uz2_51'],
                        ['uz2_38_uz2_51', 'uz2_51_uz2_64', 'uz2_64_uz2_77'],
                        ['uz2_64_uz2_77', 'uz2_77_uz2_90', 'uz2_90_uz2_103'],
                        ['uz2_90_uz2_103', 'uz2_103_uz2_116', 'uz2_116_uz2_129'],
                        ['uz2_116_uz2_129', 'uz2_129_uz2_142', 'uz2_142_uz2_155'],
                        ['uz2_142_uz2_155', 'uz2_155_uz2_168', 'uz2_168_uz1_175'],
                        ['uz2_168_uz1_175', 'uz1_175_uz1_190', 'uz1_190_uz1_191', 'uz1_191_uz1_206'],
                        ['uz1_191_uz1_206', 'uz1_206_uz1_221', 'uz1_221_uz1_222', 'uz1_222_uz0_202']
                        ],
                        TimeTable.create_table_freq('07:00:00', '12:00:00', Dt(minutes=bus_freq)))
    bus_layer.create_line('Bus_WE2',
                        ['Bus_WE2_0', 'Bus_WE2_1', 'Bus_WE2_2', 'Bus_WE2_3', 'Bus_WE2_4',
                            'Bus_WE2_5', 'Bus_WE2_6'],
                        [['uz2_10_uz2_23', 'uz2_23_uz2_36', 'uz2_36_uz2_49'],
                        ['uz2_36_uz2_49', 'uz2_49_uz2_62', 'uz2_62_uz2_75'],
                        ['uz2_62_uz2_75', 'uz2_75_uz2_88', 'uz2_88_uz2_101'],
                        ['uz2_88_uz2_101', 'uz2_101_uz2_114', 'uz2_114_uz2_127'],
                        ['uz2_114_uz2_127', 'uz2_127_uz2_140', 'uz2_140_uz2_153'],
                        ['uz2_140_uz2_153', 'uz2_153_uz2_166', 'uz2_166_uz1_174']
                        ],
                        TimeTable.create_table_freq('07:00:00', '12:00:00', Dt(minutes=bus_freq)))
    bus_layer.create_line('Bus_WE3',
                        ['Bus_WE3_0', 'Bus_WE3_1', 'Bus_WE3_2', 'Bus_WE3_3', 'Bus_WE3_4',
                            'Bus_WE3_5', 'Bus_WE3_6', 'Bus_WE3_7', 'Bus_WE3_8',
                            'Bus_WE3_9', 'Bus_WE3_10'],
                        [['uz1_10_uz1_9', 'uz1_9_uz1_24', 'uz1_24_uz1_39', 'uz1_39_uz1_38'],
                        ['uz1_39_uz1_38', 'uz1_38_uz1_53', 'uz1_53_uz2_8', 'uz2_8_uz2_21'],
                        ['uz2_8_uz2_21', 'uz2_21_uz2_34', 'uz2_34_uz2_47'],
                        ['uz2_34_uz2_47', 'uz2_47_uz2_60', 'uz2_60_uz2_73'],
                        ['uz2_60_uz2_73', 'uz2_73_uz2_86', 'uz2_86_uz2_99'],
                        ['uz2_86_uz2_99', 'uz2_99_uz2_112', 'uz2_112_uz2_125'],
                        ['uz2_112_uz2_125', 'uz2_125_uz2_138', 'uz2_138_uz2_151'],
                        ['uz2_138_uz2_151', 'uz2_151_uz2_164', 'uz2_164_uz1_173'],
                        ['uz2_164_uz1_173', 'uz1_173_uz1_188', 'uz1_188_uz1_189', 'uz1_189_uz1_204'],
                        ['uz1_189_uz1_204', 'uz1_204_uz1_219', 'uz1_219_uz1_220', 'uz1_220_uz0_201']
                        ],
                        TimeTable.create_table_freq('07:00:00', '12:00:00', Dt(minutes=bus_freq)))
    bus_layer.create_line('Bus_WE4',
                        ['Bus_WE4_0', 'Bus_WE4_1', 'Bus_WE4_2', 'Bus_WE4_3', 'Bus_WE4_4',
                            'Bus_WE4_5', 'Bus_WE4_6', 'Bus_WE4_7', 'Bus_WE4_8',
                            'Bus_WE4_9', 'Bus_WE4_10'],
                        [['uz1_4_uz1_5', 'uz1_5_uz1_20', 'uz1_20_uz1_35', 'uz1_35_uz1_36'],
                        ['uz1_35_uz1_36', 'uz1_36_uz1_51', 'uz1_51_uz2_4', 'uz2_4_uz2_17'],
                        ['uz2_4_uz2_17', 'uz2_17_uz2_30', 'uz2_30_uz2_43'],
                        ['uz2_30_uz2_43', 'uz2_43_uz2_56', 'uz2_56_uz2_69'],
                        ['uz2_56_uz2_69', 'uz2_69_uz2_82', 'uz2_82_uz2_95'],
                        ['uz2_82_uz2_95', 'uz2_95_uz2_108', 'uz2_108_uz2_121'],
                        ['uz2_108_uz2_121', 'uz2_121_uz2_134', 'uz2_134_uz2_147'],
                        ['uz2_134_uz2_147', 'uz2_147_uz2_160', 'uz2_160_uz1_171'],
                        ['uz2_160_uz1_171', 'uz1_171_uz1_186', 'uz1_186_uz1_185', 'uz1_185_uz1_200'],
                        ['uz1_185_uz1_200', 'uz1_200_uz1_215', 'uz1_215_uz1_214', 'uz1_214_uz0_198']
                        ],
                        TimeTable.create_table_freq('07:00:00', '12:00:00', Dt(minutes=bus_freq)))
    bus_layer.create_line('Bus_WE5',
                        ['Bus_WE5_0', 'Bus_WE5_1', 'Bus_WE5_2', 'Bus_WE5_3', 'Bus_WE5_4',
                            'Bus_WE5_5', 'Bus_WE5_6'],
                        [['uz2_2_uz2_15', 'uz2_15_uz2_28', 'uz2_28_uz2_41'],
                        ['uz2_28_uz2_41', 'uz2_41_uz2_54', 'uz2_54_uz2_67'],
                        ['uz2_54_uz2_67', 'uz2_67_uz2_80', 'uz2_80_uz2_93'],
                        ['uz2_80_uz2_93', 'uz2_93_uz2_106', 'uz2_106_uz2_119'],
                        ['uz2_106_uz2_119', 'uz2_119_uz2_132', 'uz2_132_uz2_145'],
                        ['uz2_132_uz2_145', 'uz2_145_uz2_158', 'uz2_158_uz1_170']
                        ],
                        TimeTable.create_table_freq('07:00:00', '12:00:00', Dt(minutes=bus_freq)))
    bus_layer.create_line('Bus_WE6',
                        ['Bus_WE6_0', 'Bus_WE6_1', 'Bus_WE6_2', 'Bus_WE6_3', 'Bus_WE6_4',
                            'Bus_WE6_5', 'Bus_WE6_6', 'Bus_WE6_7', 'Bus_WE6_8',
                            'Bus_WE6_9', 'Bus_WE6_10'],
                        [['uz1_2_uz1_3', 'uz1_3_uz1_18', 'uz1_18_uz1_33', 'uz1_33_uz1_34'],
                        ['uz1_33_uz1_34', 'uz1_34_uz1_49', 'uz1_49_uz2_0', 'uz2_0_uz2_13'],
                        ['uz2_0_uz2_13', 'uz2_13_uz2_26', 'uz2_26_uz2_39'],
                        ['uz2_26_uz2_39', 'uz2_39_uz2_52', 'uz2_52_uz2_65'],
                        ['uz2_52_uz2_65', 'uz2_65_uz2_78', 'uz2_78_uz2_91'],
                        ['uz2_78_uz2_91', 'uz2_91_uz2_104', 'uz2_104_uz2_117'],
                        ['uz2_104_uz2_117', 'uz2_117_uz2_130', 'uz2_130_uz2_143'],
                        ['uz2_130_uz2_143', 'uz2_143_uz2_156', 'uz2_156_uz1_169'],
                        ['uz2_156_uz1_169', 'uz1_169_uz1_184', 'uz1_184_uz1_183', 'uz1_183_uz1_198'],
                        ['uz1_183_uz1_198', 'uz1_198_uz1_213', 'uz1_213_uz1_212', 'uz1_212_uz0_197']
                        ],
                        TimeTable.create_table_freq('07:00:00', '12:00:00', Dt(minutes=bus_freq)))
    ## East->West
    bus_layer.create_line('Bus_EW1',
                        ['Bus_EW1_0', 'Bus_EW1_1', 'Bus_EW1_2', 'Bus_EW1_3', 'Bus_EW1_4',
                            'Bus_EW1_5', 'Bus_EW1_6', 'Bus_EW1_7', 'Bus_EW1_8',
                            'Bus_EW1_9', 'Bus_EW1_10'],
                        [['uz1_222_uz1_221', 'uz1_221_uz1_206', 'uz1_206_uz1_191', 'uz1_191_uz1_190'],
                        ['uz1_191_uz1_190', 'uz1_190_uz1_175', 'uz1_175_uz2_168', 'uz2_168_uz2_155'],
                        ['uz2_168_uz2_155', 'uz2_155_uz2_142', 'uz2_142_uz2_129'],
                        ['uz2_142_uz2_129', 'uz2_129_uz2_116', 'uz2_116_uz2_103'],
                        ['uz2_116_uz2_103', 'uz2_103_uz2_90', 'uz2_90_uz2_77'],
                        ['uz2_90_uz2_77', 'uz2_77_uz2_64', 'uz2_64_uz2_51'],
                        ['uz2_64_uz2_51', 'uz2_51_uz2_38', 'uz2_38_uz2_25'],
                        ['uz2_38_uz2_25', 'uz2_25_uz2_12', 'uz2_12_uz1_55'],
                        ['uz2_12_uz1_55', 'uz1_55_uz1_40', 'uz1_40_uz1_41', 'uz1_41_uz1_26'],
                        ['uz1_41_uz1_26', 'uz1_26_uz1_11', 'uz1_11_uz1_12', 'uz1_12_uz0_58']
                        ],
                        TimeTable.create_table_freq('07:00:00', '12:00:00', Dt(minutes=bus_freq)))
    bus_layer.create_line('Bus_EW2',
                        ['Bus_EW2_0', 'Bus_EW2_1', 'Bus_EW2_2', 'Bus_EW2_3', 'Bus_EW2_4',
                            'Bus_EW2_5', 'Bus_EW2_6'],
                        [['uz2_166_uz2_153', 'uz2_153_uz2_140', 'uz2_140_uz2_127'],
                        ['uz2_140_uz2_127', 'uz2_127_uz2_114', 'uz2_114_uz2_101'],
                        ['uz2_114_uz2_101', 'uz2_101_uz2_88', 'uz2_88_uz2_75'],
                        ['uz2_88_uz2_75', 'uz2_75_uz2_62', 'uz2_62_uz2_49'],
                        ['uz2_62_uz2_49', 'uz2_49_uz2_36', 'uz2_36_uz2_23'],
                        ['uz2_36_uz2_23', 'uz2_23_uz2_10', 'uz2_10_uz1_54']
                        ],
                        TimeTable.create_table_freq('07:00:00', '12:00:00', Dt(minutes=bus_freq)))
    bus_layer.create_line('Bus_EW3',
                        ['Bus_EW3_0', 'Bus_EW3_1', 'Bus_EW3_2', 'Bus_EW3_3', 'Bus_EW3_4',
                            'Bus_EW3_5', 'Bus_EW3_6', 'Bus_EW3_7', 'Bus_EW3_8',
                            'Bus_EW3_9', 'Bus_EW3_10'],
                        [['uz1_220_uz1_219', 'uz1_219_uz1_204', 'uz1_204_uz1_189', 'uz1_189_uz1_188'],
                        ['uz1_189_uz1_188', 'uz1_188_uz1_173', 'uz1_173_uz2_164', 'uz2_164_uz2_151'],
                        ['uz2_164_uz2_151', 'uz2_151_uz2_138', 'uz2_138_uz2_125'],
                        ['uz2_138_uz2_125', 'uz2_125_uz2_112', 'uz2_112_uz2_99'],
                        ['uz2_112_uz2_99', 'uz2_99_uz2_86', 'uz2_86_uz2_73'],
                        ['uz2_86_uz2_73', 'uz2_73_uz2_60', 'uz2_60_uz2_47'],
                        ['uz2_60_uz2_47', 'uz2_47_uz2_34', 'uz2_34_uz2_21'],
                        ['uz2_34_uz2_21', 'uz2_21_uz2_8', 'uz2_8_uz1_53'],
                        ['uz2_8_uz1_53', 'uz1_53_uz1_38', 'uz1_38_uz1_39', 'uz1_39_uz1_24'],
                        ['uz1_39_uz1_24', 'uz1_24_uz1_9', 'uz1_9_uz1_10', 'uz1_10_uz0_57'],
                        ],
                        TimeTable.create_table_freq('07:00:00', '12:00:00', Dt(minutes=bus_freq)))
    bus_layer.create_line('Bus_EW4',
                        ['Bus_EW4_0', 'Bus_EW4_1', 'Bus_EW4_2', 'Bus_EW4_3', 'Bus_EW4_4',
                            'Bus_EW4_5', 'Bus_EW4_6', 'Bus_EW4_7', 'Bus_EW4_8',
                            'Bus_EW4_9', 'Bus_EW4_10'],
                        [['uz1_214_uz1_215', 'uz1_215_uz1_200', 'uz1_200_uz1_185', 'uz1_185_uz1_186'],
                        ['uz1_185_uz1_186', 'uz1_186_uz1_171', 'uz1_171_uz2_160', 'uz2_160_uz2_147'],
                        ['uz2_160_uz2_147', 'uz2_147_uz2_134', 'uz2_134_uz2_121'],
                        ['uz2_134_uz2_121', 'uz2_121_uz2_108', 'uz2_108_uz2_95'],
                        ['uz2_108_uz2_95', 'uz2_95_uz2_82', 'uz2_82_uz2_69'],
                        ['uz2_82_uz2_69', 'uz2_69_uz2_56', 'uz2_56_uz2_43'],
                        ['uz2_56_uz2_43', 'uz2_43_uz2_30', 'uz2_30_uz2_17'],
                        ['uz2_30_uz2_17', 'uz2_17_uz2_4', 'uz2_4_uz1_51'],
                        ['uz2_4_uz1_51', 'uz1_51_uz1_36', 'uz1_36_uz1_35', 'uz1_35_uz1_20'],
                        ['uz1_35_uz1_20', 'uz1_20_uz1_5', 'uz1_5_uz1_4', 'uz1_4_uz0_54']
                        ],
                        TimeTable.create_table_freq('07:00:00', '12:00:00', Dt(minutes=bus_freq)))
    bus_layer.create_line('Bus_EW5',
                        ['Bus_EW5_0', 'Bus_EW5_1', 'Bus_EW5_2', 'Bus_EW5_3', 'Bus_EW5_4',
                            'Bus_EW5_5', 'Bus_EW5_6'],
                        [['uz2_158_uz2_145', 'uz2_145_uz2_132', 'uz2_132_uz2_119'],
                        ['uz2_132_uz2_119', 'uz2_119_uz2_106', 'uz2_106_uz2_93'],
                        ['uz2_106_uz2_93', 'uz2_93_uz2_80', 'uz2_80_uz2_67'],
                        ['uz2_80_uz2_67', 'uz2_67_uz2_54', 'uz2_54_uz2_41'],
                        ['uz2_54_uz2_41', 'uz2_41_uz2_28', 'uz2_28_uz2_15'],
                        ['uz2_28_uz2_15', 'uz2_15_uz2_2', 'uz2_2_uz1_50']
                        ],
                        TimeTable.create_table_freq('07:00:00', '12:00:00', Dt(minutes=bus_freq)))
    bus_layer.create_line('Bus_EW6',
                        ['Bus_EW6_0', 'Bus_EW6_1', 'Bus_EW6_2', 'Bus_EW6_3', 'Bus_EW6_4',
                            'Bus_EW6_5', 'Bus_EW6_6', 'Bus_EW6_7', 'Bus_EW6_8',
                            'Bus_EW6_9', 'Bus_EW6_10'],
                        [['uz1_212_uz1_213', 'uz1_213_uz1_198', 'uz1_198_uz1_183', 'uz1_183_uz1_184'],
                        ['uz1_183_uz1_184', 'uz1_184_uz1_169', 'uz1_169_uz2_156', 'uz2_156_uz2_143'],
                        ['uz2_156_uz2_143', 'uz2_143_uz2_130', 'uz2_130_uz2_117'],
                        ['uz2_130_uz2_117', 'uz2_117_uz2_104', 'uz2_104_uz2_91'],
                        ['uz2_104_uz2_91', 'uz2_91_uz2_78', 'uz2_78_uz2_65'],
                        ['uz2_78_uz2_65', 'uz2_65_uz2_52', 'uz2_52_uz2_39'],
                        ['uz2_52_uz2_39', 'uz2_39_uz2_26', 'uz2_26_uz2_13'],
                        ['uz2_26_uz2_13', 'uz2_13_uz2_0', 'uz2_0_uz1_49'],
                        ['uz2_0_uz1_49', 'uz1_49_uz1_34', 'uz1_34_uz1_33', 'uz1_33_uz1_18'],
                        ['uz1_33_uz1_18', 'uz1_18_uz1_3', 'uz1_3_uz1_2', 'uz1_2_uz0_53']
                        ],
                        TimeTable.create_table_freq('07:00:00', '12:00:00', Dt(minutes=bus_freq)))
    ### Feeder bus
    ## North
    bus_layer.create_line('Bus_feederN1',
                        ['Bus_feederN1_0', 'Bus_feederN1_1', 'Bus_feederN1_2', 'Bus_feederN1_3', 'Bus_feederN1_4'],
                        [['uz0_124_uz1_104', 'uz1_104_uz1_103'],
                        ['uz1_104_uz1_103', 'uz1_103_uz1_102', 'uz1_102_uz1_117', 'uz1_117_uz1_132'],
                        ['uz1_117_uz1_132', 'uz1_132_uz1_133', 'uz1_133_uz1_134', 'uz1_134_uz0_140'],
                        ['uz1_134_uz0_140', 'uz0_140_uz0_124b']
                        ],
                        TimeTable.create_table_freq('07:00:00', '12:00:00', Dt(minutes=feederbus_freq)))
    bus_layer.create_line('Bus_feederN2',
                        ['Bus_feederN2_0', 'Bus_feederN2_1', 'Bus_feederN2_2', 'Bus_feederN2_3', 'Bus_feederN2_4'],
                        [['uz0_140_uz1_134', 'uz1_134_uz1_133'],
                        ['uz1_134_uz1_133', 'uz1_133_uz1_132', 'uz1_132_uz1_117', 'uz1_117_uz1_102'],
                        ['uz1_117_uz1_102', 'uz1_102_uz1_103', 'uz1_103_uz1_104', 'uz1_104_uz0_124'],
                        ['uz1_104_uz0_124', 'uz0_124_uz0_124b']
                        ],
                        TimeTable.create_table_freq('07:00:00', '12:00:00', Dt(minutes=feederbus_freq)))
    bus_layer.create_line('Bus_feederNWE',
                        ['Bus_feederNWE_0', 'Bus_feederNWE_1', 'Bus_feederNWE_2', 'Bus_feederNWE_3', 'Bus_feederNWE_4', 'Bus_feederNWE_5', 'Bus_feederNWE_6'],
                        [['uz0_46_uz0_62', 'uz0_62_uz0_78', 'uz0_78_uz0_94'],
                        ['uz0_78_uz0_94', 'uz0_94_uz0_110', 'uz0_110_uz0_126'],
                        ['uz0_110_uz0_126', 'uz0_126_uz0_126b', 'uz0_126b_uz0_142'],
                        ['uz0_126b_uz0_142', 'uz0_142_uz0_158', 'uz0_158_uz0_174'],
                        ['uz0_158_uz0_174', 'uz0_174_uz0_190', 'uz0_190_uz0_206'],
                        ['uz0_190_uz0_206', 'uz0_206_uz0_222', 'uz0_222_uz0_238']
                        ],
                        TimeTable.create_table_freq('07:00:00', '12:00:00', Dt(minutes=feederbus_freq)))
    bus_layer.create_line('Bus_feederNEW',
                        ['Bus_feederNEW_0', 'Bus_feederNEW_1', 'Bus_feederNEW_2', 'Bus_feederNEW_3', 'Bus_feederNEW_4', 'Bus_feederNEW_5', 'Bus_feederNEW_6'],
                        [['uz0_222_uz0_206', 'uz0_206_uz0_190', 'uz0_190_uz0_174'],
                        ['uz0_190_uz0_174', 'uz0_174_uz0_158', 'uz0_158_uz0_142'],
                        ['uz0_158_uz0_142', 'uz0_142_uz0_126b', 'uz0_126b_uz0_126'],
                        ['uz0_126b_uz0_126', 'uz0_126_uz0_110', 'uz0_110_uz0_94'],
                        ['uz0_110_uz0_94', 'uz0_94_uz0_78', 'uz0_78_uz0_62'],
                        ['uz0_78_uz0_62', 'uz0_62_uz0_46', 'uz0_46_uz0_30']
                        ],
                        TimeTable.create_table_freq('07:00:00', '12:00:00', Dt(minutes=feederbus_freq)))
    ## South
    bus_layer.create_line('Bus_feederS1',
                        ['Bus_feederS1_0', 'Bus_feederS1_1', 'Bus_feederS1_2', 'Bus_feederS1_3', 'Bus_feederS1_4'],
                        [['uz0_131_uz1_120', 'uz1_120_uz1_121'],
                        ['uz1_120_uz1_121', 'uz1_121_uz1_122', 'uz1_122_uz1_107', 'uz1_107_uz1_92'],
                        ['uz1_107_uz1_92', 'uz1_92_uz1_91', 'uz1_91_uz1_90', 'uz1_90_uz0_115'],
                        ['uz1_90_uz0_115', 'uz0_115_uz0_115b']
                        ],
                        TimeTable.create_table_freq('07:00:00', '12:00:00', Dt(minutes=feederbus_freq)))
    bus_layer.create_line('Bus_feederS2',
                        ['Bus_feederS2_0', 'Bus_feederS2_1', 'Bus_feederS2_2', 'Bus_feederS2_3', 'Bus_feederS2_4'],
                        [['uz0_115_uz1_90', 'uz1_90_uz1_91'],
                        ['uz1_90_uz1_91', 'uz1_91_uz1_92', 'uz1_92_uz1_107', 'uz1_107_uz1_122'],
                        ['uz1_107_uz1_122', 'uz1_122_uz1_121', 'uz1_121_uz1_120', 'uz1_120_uz0_131'],
                        ['uz1_120_uz0_131', 'uz0_131_uz0_115b']
                        ],
                        TimeTable.create_table_freq('07:00:00', '12:00:00', Dt(minutes=feederbus_freq)))
    bus_layer.create_line('Bus_feederSWE',
                        ['Bus_feederSWE_0', 'Bus_feederSWE_1', 'Bus_feederSWE_2', 'Bus_feederSWE_3', 'Bus_feederSWE_4', 'Bus_feederSWE_5', 'Bus_feederSWE_6'],
                        [['uz0_33_uz0_49', 'uz0_49_uz0_65', 'uz0_65_uz0_81'],
                        ['uz0_65_uz0_81', 'uz0_81_uz0_97', 'uz0_97_uz0_113'],
                        ['uz0_97_uz0_113', 'uz0_113_uz0_113b', 'uz0_113b_uz0_129'],
                        ['uz0_113b_uz0_129', 'uz0_129_uz0_145', 'uz0_145_uz0_161'],
                        ['uz0_145_uz0_161', 'uz0_161_uz0_177', 'uz0_177_uz0_193'],
                        ['uz0_177_uz0_193', 'uz0_193_uz0_209', 'uz0_209_uz0_225']
                        ],
                        TimeTable.create_table_freq('07:00:00', '12:00:00', Dt(minutes=feederbus_freq)))
    bus_layer.create_line('Bus_feederSEW',
                        ['Bus_feederSEW_0', 'Bus_feederSEW_1', 'Bus_feederSEW_2', 'Bus_feederSEW_3', 'Bus_feederSEW_4', 'Bus_feederSEW_5', 'Bus_feederSEW_6'],
                        [['uz0_209_uz0_193', 'uz0_193_uz0_177', 'uz0_177_uz0_161'],
                        ['uz0_177_uz0_161', 'uz0_161_uz0_145', 'uz0_145_uz0_129'],
                        ['uz0_145_uz0_129', 'uz0_129_uz0_113b', 'uz0_113b_uz0_113'],
                        ['uz0_113b_uz0_113', 'uz0_113_uz0_97', 'uz0_97_uz0_81'],
                        ['uz0_97_uz0_81', 'uz0_81_uz0_65', 'uz0_65_uz0_49'],
                        ['uz0_65_uz0_49', 'uz0_49_uz0_33', 'uz0_33_uz0_17']
                        ],
                        TimeTable.create_table_freq('07:00:00', '12:00:00', Dt(minutes=feederbus_freq)))
    ## West
    bus_layer.create_line('Bus_feederW1',
                        ['Bus_feederW1_0', 'Bus_feederW1_1', 'Bus_feederW1_2', 'Bus_feederW1_3', 'Bus_feederW1_4'],
                        [['uz0_55_uz1_6', 'uz1_6_uz1_21'],
                        ['uz1_6_uz1_21', 'uz1_21_uz1_36', 'uz1_36_uz1_37', 'uz1_37_uz1_38'],
                        ['uz1_37_uz1_38', 'uz1_38_uz1_23', 'uz1_23_uz1_8', 'uz1_8_uz0_56'],
                        ['uz1_8_uz0_56', 'uz0_56_uz0_55b']
                        ],
                        TimeTable.create_table_freq('07:00:00', '12:00:00', Dt(minutes=feederbus_freq)))
    bus_layer.create_line('Bus_feederW2',
                        ['Bus_feederW2_0', 'Bus_feederW2_1', 'Bus_feederW2_2', 'Bus_feederW2_3', 'Bus_feederW2_4'],
                        [['uz0_56_uz1_8', 'uz1_8_uz1_23'],
                        ['uz1_8_uz1_23', 'uz1_23_uz1_38', 'uz1_38_uz1_37', 'uz1_37_uz1_36'],
                        ['uz1_37_uz1_36', 'uz1_36_uz1_21', 'uz1_21_uz1_6', 'uz1_6_uz0_55'],
                        ['uz1_6_uz0_55', 'uz0_55_uz0_55b']
                        ],
                        TimeTable.create_table_freq('07:00:00', '12:00:00', Dt(minutes=feederbus_freq)))
    bus_layer.create_line('Bus_feederWNS',
                        ['Bus_feederWNS_0', 'Bus_feederWNS_1', 'Bus_feederWNS_2', 'Bus_feederWNS_3', 'Bus_feederWNS_4', 'Bus_feederWNS_5', 'Bus_feederWNS_6'],
                        [['uz0_29_uz0_28', 'uz0_28_uz0_27', 'uz0_27_uz0_26'],
                        ['uz0_27_uz0_26', 'uz0_26_uz0_25', 'uz0_25_uz0_24'],
                        ['uz0_25_uz0_24', 'uz0_24_uz0_23b', 'uz0_23b_uz0_23'],
                        ['uz0_23b_uz0_23', 'uz0_23_uz0_22', 'uz0_22_uz0_21'],
                        ['uz0_22_uz0_21', 'uz0_21_uz0_20', 'uz0_20_uz0_19'],
                        ['uz0_20_uz0_19', 'uz0_19_uz0_18', 'uz0_18_uz0_17']
                        ],
                        TimeTable.create_table_freq('07:00:00', '12:00:00', Dt(minutes=feederbus_freq)))
    bus_layer.create_line('Bus_feederWSN',
                        ['Bus_feederWSN_0', 'Bus_feederWSN_1', 'Bus_feederWSN_2', 'Bus_feederWSN_3', 'Bus_feederWSN_4', 'Bus_feederWSN_5', 'Bus_feederWSN_6'],
                        [['uz0_18_uz0_19', 'uz0_19_uz0_20', 'uz0_20_uz0_21'],
                        ['uz0_20_uz0_21', 'uz0_21_uz0_22', 'uz0_22_uz0_23'],
                        ['uz0_22_uz0_23', 'uz0_23_uz0_23b', 'uz0_23b_uz0_24'],
                        ['uz0_23b_uz0_24', 'uz0_24_uz0_25', 'uz0_25_uz0_26'],
                        ['uz0_25_uz0_26', 'uz0_26_uz0_27', 'uz0_27_uz0_28'],
                        ['uz0_27_uz0_28', 'uz0_28_uz0_29', 'uz0_29_uz0_30']
                        ],
                        TimeTable.create_table_freq('07:00:00', '12:00:00', Dt(minutes=feederbus_freq)))
    ## East
    bus_layer.create_line('Bus_feederE1',
                        ['Bus_feederE1_0', 'Bus_feederE1_1', 'Bus_feederE1_2', 'Bus_feederE1_3', 'Bus_feederE1_4'],
                        [['uz0_200_uz1_218', 'uz1_218_uz1_203'],
                        ['uz1_218_uz1_203', 'uz1_203_uz1_188', 'uz1_188_uz1_187', 'uz1_187_uz1_186'],
                        ['uz1_187_uz1_186', 'uz1_186_uz1_201', 'uz1_201_uz1_216', 'uz1_216_uz0_199'],
                        ['uz1_216_uz0_199', 'uz0_199_uz0_199b']
                        ],
                        TimeTable.create_table_freq('07:00:00', '12:00:00', Dt(minutes=feederbus_freq)))
    bus_layer.create_line('Bus_feederE2',
                        ['Bus_feederE2_0', 'Bus_feederE2_1', 'Bus_feederE2_2', 'Bus_feederE2_3', 'Bus_feederE2_4'],
                        [['uz0_199_uz1_216', 'uz1_216_uz1_201'],
                        ['uz1_216_uz1_201', 'uz1_201_uz1_186', 'uz1_186_uz1_187', 'uz1_187_uz1_188'],
                        ['uz1_187_uz1_188', 'uz1_188_uz1_203', 'uz1_203_uz1_218', 'uz1_218_uz0_200'],
                        ['uz1_218_uz0_200', 'uz0_200_uz0_199b']
                        ],
                        TimeTable.create_table_freq('07:00:00', '12:00:00', Dt(minutes=feederbus_freq)))
    bus_layer.create_line('Bus_feederENS',
                        ['Bus_feederENS_0', 'Bus_feederENS_1', 'Bus_feederENS_2', 'Bus_feederENS_3', 'Bus_feederENS_4', 'Bus_feederENS_5', 'Bus_feederENS_6'],
                        [['uz0_237_uz0_236', 'uz0_236_uz0_235', 'uz0_235_uz0_234'],
                        ['uz0_235_uz0_234', 'uz0_234_uz0_233', 'uz0_233_uz0_232'],
                        ['uz0_233_uz0_232', 'uz0_232_uz0_231b', 'uz0_231b_uz0_231'],
                        ['uz0_231b_uz0_231', 'uz0_231_uz0_230', 'uz0_230_uz0_229'],
                        ['uz0_230_uz0_229', 'uz0_229_uz0_228', 'uz0_228_uz0_227'],
                        ['uz0_228_uz0_227', 'uz0_227_uz0_226', 'uz0_226_uz0_225']
                        ],
                        TimeTable.create_table_freq('07:00:00', '12:00:00', Dt(minutes=feederbus_freq)))
    bus_layer.create_line('Bus_feederESN',
                        ['Bus_feederESN_0', 'Bus_feederESN_1', 'Bus_feederESN_2', 'Bus_feederESN_3', 'Bus_feederESN_4', 'Bus_feederESN_5', 'Bus_feederESN_6'],
                        [['uz0_226_uz0_227', 'uz0_227_uz0_228', 'uz0_228_uz0_229'],
                        ['uz0_228_uz0_229', 'uz0_229_uz0_230', 'uz0_230_uz0_231'],
                        ['uz0_230_uz0_231', 'uz0_231_uz0_231b', 'uz0_231b_uz0_232'],
                        ['uz0_231b_uz0_232', 'uz0_232_uz0_233', 'uz0_233_uz0_234'],
                        ['uz0_233_uz0_234', 'uz0_234_uz0_235', 'uz0_235_uz0_236'],
                        ['uz0_235_uz0_236', 'uz0_236_uz0_237', 'uz0_237_uz0_238']
                        ],
                        TimeTable.create_table_freq('07:00:00', '12:00:00', Dt(minutes=feederbus_freq)))
    ### Metro
    ## North->South
    metro_layer.create_line('Metro_NS',
                        ['Metro_NS_0', 'Metro_NS_1', 'Metro_NS_2', 'Metro_NS_3', 'Metro_NS_4',
                        'Metro_NS_5', 'Metro_NS_6', 'Metro_NS_7', 'Metro_NS_8'],
                        [['uz1_117_uz1_116', 'uz1_116_uz2_90', 'uz2_90_uz2_89'],
                        ['uz2_90_uz2_89', 'uz2_89_uz2_88', 'uz2_88_uz2_87'],
                        ['uz2_88_uz2_87', 'uz2_87_uz2_86', 'uz2_86_uz2_85'],
                        ['uz2_86_uz2_85', 'uz2_85_uz2_84', 'uz2_84_uz2_83'],
                        ['uz2_84_uz2_83', 'uz2_83_uz2_82', 'uz2_82_uz2_81'],
                        ['uz2_82_uz2_81', 'uz2_81_uz2_80', 'uz2_80_uz2_79'],
                        ['uz2_80_uz2_79', 'uz2_79_uz2_78', 'uz2_78_uz1_108'],
                        ['uz2_78_uz1_108', 'uz1_108_uz1_107', 'uz1_107_uz1_106']
                        ],
                        TimeTable.create_table_freq('07:00:00', '12:00:00', Dt(minutes=metro_freq)))
    ## South->North
    metro_layer.create_line('Metro_SN',
                        ['Metro_SN_0', 'Metro_SN_1', 'Metro_SN_2', 'Metro_SN_3', 'Metro_SN_4',
                        'Metro_SN_5', 'Metro_SN_6', 'Metro_SN_7', 'Metro_SN_8'],
                        [['uz1_107_uz1_108', 'uz1_108_uz2_78', 'uz2_78_uz2_79'],
                        ['uz2_78_uz2_79', 'uz2_79_uz2_80', 'uz2_80_uz2_81'],
                        ['uz2_80_uz2_81', 'uz2_81_uz2_82', 'uz2_82_uz2_83'],
                        ['uz2_82_uz2_83', 'uz2_83_uz2_84', 'uz2_84_uz2_85'],
                        ['uz2_84_uz2_85', 'uz2_85_uz2_86', 'uz2_86_uz2_87'],
                        ['uz2_86_uz2_87', 'uz2_87_uz2_88', 'uz2_88_uz2_89'],
                        ['uz2_88_uz2_89', 'uz2_89_uz2_90', 'uz2_90_uz1_116'],
                        ['uz2_90_uz1_116', 'uz1_116_uz1_117', 'uz1_117_uz1_118']
                        ],
                        TimeTable.create_table_freq('07:00:00', '12:00:00', Dt(minutes=metro_freq)))
    ## West->East
    metro_layer.create_line('Metro_WE',
                        ['Metro_WE_0', 'Metro_WE_1', 'Metro_WE_2', 'Metro_WE_3', 'Metro_WE_4',
                        'Metro_WE_5', 'Metro_WE_6', 'Metro_WE_7', 'Metro_WE_8'],
                        [['uz1_37_uz1_52', 'uz1_52_uz2_6', 'uz2_6_uz2_19'],
                        ['uz2_6_uz2_19', 'uz2_19_uz2_32', 'uz2_32_uz2_45'],
                        ['uz2_32_uz2_45', 'uz2_45_uz2_58', 'uz2_58_uz2_71'],
                        ['uz2_58_uz2_71', 'uz2_71_uz2_84', 'uz2_84_uz2_97'],
                        ['uz2_84_uz2_97', 'uz2_97_uz2_110', 'uz2_110_uz2_123'],
                        ['uz2_110_uz2_123', 'uz2_123_uz2_136', 'uz2_136_uz2_149'],
                        ['uz2_136_uz2_149', 'uz2_149_uz2_162', 'uz2_162_uz1_172'],
                        ['uz2_162_uz1_172', 'uz1_172_uz1_187', 'uz1_187_uz1_202']
                        ],
                        TimeTable.create_table_freq('07:00:00', '12:00:00', Dt(minutes=metro_freq)))
    ## East->West
    metro_layer.create_line('Metro_EW',
                        ['Metro_EW_0', 'Metro_EW_1', 'Metro_EW_2', 'Metro_EW_3', 'Metro_EW_4',
                        'Metro_EW_5', 'Metro_EW_6', 'Metro_EW_7', 'Metro_EW_8'],
                        [['uz1_187_uz1_172', 'uz1_172_uz2_162', 'uz2_162_uz2_149'],
                        ['uz2_162_uz2_149', 'uz2_149_uz2_136', 'uz2_136_uz2_123'],
                        ['uz2_136_uz2_123', 'uz2_123_uz2_110', 'uz2_110_uz2_97'],
                        ['uz2_110_uz2_97', 'uz2_97_uz2_84', 'uz2_84_uz2_71'],
                        ['uz2_84_uz2_71', 'uz2_71_uz2_58', 'uz2_58_uz2_45'],
                        ['uz2_58_uz2_45', 'uz2_45_uz2_32', 'uz2_32_uz2_19'],
                        ['uz2_32_uz2_19', 'uz2_19_uz2_6', 'uz2_6_uz1_52'],
                        ['uz2_6_uz1_52', 'uz1_52_uz1_37', 'uz1_37_uz1_22']
                        ],
                        TimeTable.create_table_freq('07:00:00', '12:00:00', Dt(minutes=metro_freq)))

    ### Train
    ## North -> South
    train_layer.create_line('Train_NS',
                        ['Train_NS_0', 'Train_NS_1', 'Train_NS_2', 'Train_NS_3', 'Train_NS_4',
                        'Train_NS_5', 'Train_NS_6'],
                        [['Rail_1_Rail_2', 'Rail_2_Rail_3'],
                        ['Rail_2_Rail_3', 'Rail_3_Rail_4'],
                        ['Rail_3_Rail_4', 'Rail_4_Rail_5'],
                        ['Rail_4_Rail_5', 'Rail_5_Rail_6'],
                        ['Rail_5_Rail_6', 'Rail_6_Rail_7'],
                        ['Rail_6_Rail_7']
                        ],
                        TimeTable.create_table_freq('07:00:00', '12:00:00', Dt(minutes=train_freq)))
    ## South -> North
    train_layer.create_line('Train_SN',
                        ['Train_SN_0', 'Train_SN_1', 'Train_SN_2', 'Train_SN_3', 'Train_SN_4',
                        'Train_SN_5', 'Train_SN_6'],
                        [['Rail_7_Rail_6', 'Rail_6_Rail_5'],
                        ['Rail_6_Rail_5', 'Rail_5_Rail_4'],
                        ['Rail_5_Rail_4', 'Rail_4_Rail_3'],
                        ['Rail_4_Rail_3', 'Rail_3_Rail_2'],
                        ['Rail_3_Rail_2', 'Rail_2_Rail_1'],
                        ['Rail_2_Rail_1']
                        ],
                        TimeTable.create_table_freq('07:00:00', '12:00:00', Dt(minutes=train_freq)))

    ## West -> East
    train_layer.create_line('Train_WE',
                        ['Train_WE_0', 'Train_WE_1', 'Train_WE_2', 'Train_WE_3', 'Train_WE_4',
                        'Train_WE_5', 'Train_WE_6'],
                        [['Rail_8_Rail_9', 'Rail_9_Rail_10'],
                        ['Rail_9_Rail_10', 'Rail_10_Rail_4'],
                        ['Rail_10_Rail_4', 'Rail_4_Rail_11'],
                        ['Rail_4_Rail_11', 'Rail_11_Rail_12'],
                        ['Rail_11_Rail_12', 'Rail_12_Rail_13'],
                        ['Rail_12_Rail_13']
                        ],
                        TimeTable.create_table_freq('07:00:00', '12:00:00', Dt(minutes=train_freq)))

    ## East -> West
    train_layer.create_line('Train_EW',
                        ['Train_EW_0', 'Train_EW_1', 'Train_EW_2', 'Train_EW_3', 'Train_EW_4',
                        'Train_EW_5', 'Train_EW_6'],
                        [['Rail_13_Rail_12', 'Rail_12_Rail_11'],
                        ['Rail_12_Rail_11', 'Rail_11_Rail_4'],
                        ['Rail_11_Rail_4', 'Rail_4_Rail_10'],
                        ['Rail_4_Rail_10', 'Rail_10_Rail_9'],
                        ['Rail_10_Rail_9', 'Rail_9_Rail_8'],
                        ['Rail_9_Rail_8']
                        ],
                        TimeTable.create_table_freq('07:00:00', '12:00:00', Dt(minutes=train_freq)))
