import os
import json
import csv
from shapely import geometry
from shapely.geometry import LineString, Point
from matplotlib import pyplot

# Parse Reservoir son
reservoirFilePath = "\Lyon10Res.json"
reservoirFile = open(os.getcwd( ) +reservoirFilePath, 'r')
reservoirJson = json.load(reservoirFile)
reservoirs = reservoirJson['RESERVOIRS']

# Parse links csv
linksFilePath = "\Lyon_Links.csv"
linksFile = open(os.getcwd( ) +linksFilePath, 'r')
linksCsv = csv.reader(linksFile, delimiter=';')
links = []
for link in linksCsv:
    links.append(link)

reservoirPolygons = []
for count, reservoir in enumerate(reservoirs):
    numRes = count+1
    pointList = []
    for borderPoint in reservoir['BorderPoints']:
        x = borderPoint['x']
        y = borderPoint['y']
        point = Point(x, y)
        pointList.append(point)
    polygon = geometry.Polygon([[p.x, p.y] for p in pointList])

    if polygon.is_valid:
        print("Reservoir/Polygone valide ", numRes)
    else:
        print("Reservoir/Polygone invalide ", numRes)
        # tolerance = 0
        # while not polygon.is_valid:
        #     print("Reservoir/Polygone invalide ", numRes, "Simplify with tolerance ", tolerance)
        #     polygon.simplify(tolerance, preserve_topology=True)
        #     tolerance += 10
        # if polygon.is_valid:
        #     print("Reservoir/Polygone valide ", numRes)

    reservoirPolygons.append(polygon)

# Build output csv
header = ['id_lien', 'id_reservoir']
data = []

# dessin/plot des reservoirs
pyplot.figure(numRes, figsize=(10,10), dpi=90)
for polygon in reservoirPolygons:
    xp,yp = polygon.exterior.xy
    pyplot.plot(xp,yp)


for link in links:
    # Récupération identifiant du lien
    idLien = link[0]

    # Récupération des coordonnées x et y des points amont et aval
    x_amont = link[1]
    y_amont = link[2]
    x_aval = link[3]
    y_aval = link[4]

    pointAmont = Point(float(x_amont), float(y_amont))
    pointAval = Point(float(x_aval), float(y_aval))

    idReservoir = "Res0"
    idReservoirAmont = "Res0"
    idReservoirAval = "Res0"
    reservoirAmont = geometry.Polygon()
    reservoirAval = geometry.Polygon()

    for count, reservoir in enumerate(reservoirPolygons):
        numRes = count + 1
        if reservoir.contains(pointAmont):
            idReservoirAmont = "Res"+str(numRes)
            reservoirAmont = reservoir
        if reservoir.contains(pointAval):
            idReservoirAval = "Res"+str(numRes)
            reservoirAval = reservoir

    if idReservoirAmont == idReservoirAval:
        idReservoir = idReservoirAmont

    # Code initial avec les vrais polygones
    else:
        # Tracé du lien: une ligne entre le point amont et le point aval
        ligneAmontAval = LineString([pointAmont, pointAval])

        # point d'intersection entre le lien et le bord du reservoir amont
        if reservoirAmont.is_valid:
            pti_am = ligneAmontAval.intersection(reservoirAmont)
        else:
            print("Reservoir/Polygone (amont) invalide : " + idReservoirAmont)

        # point d'intersection entre le lien et le bord du reservoir aval
        if reservoirAval.is_valid:
            pti_av = ligneAmontAval.intersection(reservoirAval)
        else:
            print("Reservoir/Polygone (aval) invalide : " + idReservoirAval)

        # distance entre le point amont et le point d'intersection lien/reservoir amont
        distAm = pointAmont.distance(pti_am)
        # distance entre le point aval et le point d'intersection lien/reservoir aval
        distAv = pointAval.distance(pti_av)

        # prendre le reservoir dont la distance est la plus longue
        if distAm >= distAv:
            idReservoir = idReservoirAmont
        else:
            idReservoir = idReservoirAval

    # Si point amont dans aucun réservoir : prendre le reservoir aval
    if idReservoirAmont == "Res0" and idReservoirAval != "Res0":
        idReservoir = idReservoirAval

    # Si point aval dans aucun réservoir : prendre le reservoir amont
    if idReservoirAval == "Res0" and idReservoirAmont != "Res0":
        idReservoir = idReservoirAmont

    # dessin/plot des points (amont/aval) des liens qui ne se trouve pas dans un réservoir
    if idReservoirAmont == idReservoirAval and idReservoirAmont == "Res0":
        pyplot.plot(float(x_amont), float(y_amont), 'ro')
        pyplot.plot(float(x_aval), float(y_aval), 'ro')

    dataEntry = [idLien, idReservoir]
    data.append(dataEntry)

pyplot.show()

# write output csv
outFilePath = 'fichier_liens.csv'
outFile = open(outFilePath, 'w', encoding='UTF8', newline='')

writer = csv.writer(outFile, delimiter=';', quotechar='|')

# write the header
writer.writerow(header)

# write multiple rows
writer.writerows(data)

# close files
reservoirFile.close()
linksFile.close()
outFile.close()