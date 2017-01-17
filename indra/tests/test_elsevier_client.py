from indra.literature import elsevier_client as ec

def test_get_fulltext_article():
    # This article is not open access so in order to get a full text response
    # with a body element requires full text access keys to be correctly
    # set up.
    doi = '10.1016/j.cell.2016.02.059'
    text = ec.get_article(doi)
    assert text is not None

def test_get_abstract():
    # If we have an API key but are not on an approved IP or don't have a
    # necessary institution key, we should still be able to get the abstract.
    # If there is a problem with the API key itself, this will log and error
    # and return None.
    doi = '10.1016/j.cell.2016.02.059'
    text = ec.get_abstract(doi)
    assert text is not None
