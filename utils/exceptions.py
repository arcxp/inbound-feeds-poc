class MismatchedContentTypeException(Exception):
    pass


class IncompleteWireStoryException(Exception):
    def __init__(self, message="Wire story cannot be sent to Draft API without ans and circulation and operations data"):
        self.message = message
        super().__init__(self.message)


class IncompleteWirePhotoException(Exception):
    def __init__(self, message="Wire photo cannot be sent to Photo API without ans data"):
        self.message = message
        super().__init__(self.message)


class WireExistsInArcException(Exception):
    def __init__(
        self,
        message="Wire's sha1 exists in inventory and is the same as the sha1 generated from the ap data. Wire has no changes in its source, so ans will not be generated.",
    ):
        self.message = message
        super().__init__(self.message)
