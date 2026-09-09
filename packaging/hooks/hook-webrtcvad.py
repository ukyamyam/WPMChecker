from PyInstaller.utils.hooks import copy_metadata

# The import is named `webrtcvad`, while the maintained wheel distribution is
# named `webrtcvad-wheels`. PyInstaller's contrib hook still asks for metadata
# under the old distribution name and fails on current releases.
datas = copy_metadata("webrtcvad-wheels")
hiddenimports = ["_webrtcvad"]
