'''
An example pytest file.  To run, setup conda environment then run pytest on commandline.

From https://realpython.com/pytest-python-testing/
'''

# Example function to test (would normally be in another file)
def format_data_for_display(people):
    results = []

    for person in people:
        given_name = person["given_name"]
        family_name = person["family_name"]
        title = person["title"]
        results.append(f"{given_name} {family_name}: {title}")

    return results


def test_format_data_for_display():
    people = [
        {
            "given_name": "Alfonsa",
            "family_name": "Ruiz",
            "title": "Senior Software Engineer",
        },
        {
            "given_name": "Sayid",
            "family_name": "Khan",
            "title": "Project Manager",
        },
    ]

    assert format_data_for_display(people) == [
        "Alfonsa Ruiz: Senior Software Engineer",
        "Sayid Khan: Project Manager",
    ]
