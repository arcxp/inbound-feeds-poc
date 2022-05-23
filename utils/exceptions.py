class MismatchedContentTypeException(Exception):
    pass


class IncompleteWireStoryException(Exception):
    def __init__(self, message="Wire story cannot be sent to Draft API without ans and circulation and operations data"):
        self.message = message
        super().__init__(self.message)


class IncompleteWirePhotoException(Exception):
    def __init__(self, message="Wire photo cannot be sent to Draft API without ans data"):
        self.message = message
        super().__init__(self.message)


class WirePhotoExistsInArcException(Exception):
    def __init__(
        self,
        message="Wire photo sha1 exists in inventory and is the same as the sha1 generated from the ap photo data. Wire photo has no changes in its source properties, so ans will not be generated.",
    ):
        self.message = message
        super().__init__(self.message)
