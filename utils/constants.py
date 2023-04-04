AP_RESULTS_JMESPATH_STR = 'data.items[*].item.{"type": type, "source_id": altids.itemid, "url": uri, "headline": headline, "bylines": bylines, "firstcreated": firstcreated, "versioncreated": versioncreated, "originalfilename": renditions.main.originalfilename, "description_caption": description_caption, "download_url": renditions.main.href || renditions.nitf.href, "associations": associations, "priced": renditions.main.priced, "pricetag": renditions.main.pricetag}'

AP_ASSOCIATIONS_JMESPATH_STR = 'data.item.{"type": type, "source_id": altids.itemid, "url": uri, "headline": headline, "bylines": bylines, "firstcreated": firstcreated, "versioncreated": versioncreated, "originalfilename": renditions.main.originalfilename, "description_caption": description_caption, "download_url": renditions.main.href}'

DRAFT_API_URL = "https://api.{org}.arcpublishing.com/draft/v1/story"

CIRCULATION_URL = "https://api.{org}.arcpublishing.com/draft/v1/story/{arc_id}/circulation/{website}"

OPERATIONS_URL = "https://api.{org}.arcpublishing.com/contentops/v1/delete"

PHOTO_API_URL = "https://api.{org}.arcpublishing.com/photo/api/v2/photos/{arc_id}"

# This example inbound wires adapter is not using the Draft API PUBLISH endpoint, following the best practice of
# importing wire content as unpublished only.  Wire content would then be selected by the newsroom and published
# as needed. This conserves the Draft API rate limit and protects from unnecessary calls to the Draft API publish endpoint.