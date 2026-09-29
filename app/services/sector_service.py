def get_sector_options(project):
    return project.get("sectors", [])


def add_sector(project, sector):
    project["sectors"].append(sector)
