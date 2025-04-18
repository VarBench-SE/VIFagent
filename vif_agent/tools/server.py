from vif_agent.feature import CodeImageMapping, MappedCode

from typing import Any
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp import FastMCP, Image
from vif_agent.renderer.tex_renderer import TexRenderer
import uuid
import os

# Create an MCP server
mcp = FastMCP("Vif")
renderer = TexRenderer()

tmp_edit_folder = os.path.join(".tmp", uuid.uuid4())
os.mkdir(tmp_edit_folder)


@mcp.tool()
def render_tikz_code(tikz_code_filename: str, output_filename: str) -> Image:
    """Create a image from TikZ code from a specified file
    The output_path is the name of the image that will be written.
    """
    output_filename = os.path.join(
        tmp_edit_folder, ".".join(output_filename.split(".")[:-1]) + ".png"
    )
    tikz_code_filename = os.path.join(tmp_edit_folder, tikz_code_filename)
    img = renderer.from_string_to_image(tikz_code_filename)
    img.save(output_filename)
    return f"Image written to {output_filename}"


import base64


@mcp.tool
def get_feature_location(tikz_code_filename: str):
    pass


if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport="stdio")
