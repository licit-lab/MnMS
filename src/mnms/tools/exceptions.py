class DuplicateNodesError(Exception):
    def __init__(self, nids:set):
        msg = f'Nodes {nids} are not unique'
        super().__init__(msg)


class DuplicateLinksError(Exception):
    def __init__(self, lids:set):
        msg = f'Links {lids} are not unique'
        super().__init__(msg)


class PathNotFound(Exception):
    def __init__(self, origin, destination):
        msg = f'No paths has been found between {origin} -> {destination}'
        super().__init__(msg)


class VehicleNotFoundError(Exception):
    def __init__(self, user, mobility_service):
        msg = f"{mobility_service.id} did not found any vehicle for {user}"
        super().__init__(msg)


class CSVDemandParseError(Exception):
    def __init__(self, file):
        msg = f"Cannot parse the origin or destination for demand_type for the file {file}"
        super(CSVDemandParseError, self).__init__(msg)