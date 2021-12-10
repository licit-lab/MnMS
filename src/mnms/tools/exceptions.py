class DuplicateNodesError(Exception):
    def __init__(self, nids:set):
        msg = f'Nodes {nids} are not unique'
        super().__init__(msg)


class DuplicateLinksError(Exception):
    def __init__(self, lids:set):
        msg = f'Links {lids} are not unique'
        super().__init__(msg)
