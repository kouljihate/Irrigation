import ezdxf


def export_project_to_dxf(project, output_path):
    document = ezdxf.new("R2010")

    document.layers.new("LAND_BOUNDARY", dxfattribs={"color": 7})
    document.layers.new("SECTORS", dxfattribs={"color": 4})
    document.layers.new("ZONES", dxfattribs={"color": 6})
    document.layers.new("PIPE_90", dxfattribs={"color": 1})
    document.layers.new("PIPE_63", dxfattribs={"color": 5})
    document.layers.new("PIPE_32", dxfattribs={"color": 3})
    document.layers.new("DRIP_16", dxfattribs={"color": 8})
    document.layers.new("VALVES", dxfattribs={"color": 2})
    document.layers.new("TREES", dxfattribs={"color": 94})

    document.saveas(output_path)
