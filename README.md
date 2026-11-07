BAS1C AI IMAGE RENAMER
======================

WHAT THIS DOES
- Choose one image, or choose a folder.
- Uses a local Ollama vision model (default: minicpm-v).
- Produces descriptive filenames based on image content.
- Shows a preview before renaming.
- Preserves each original extension.
- Never overwrites an existing file.
- Writes a preview CSV, final report CSV, and JSON plan.

REQUIREMENTS
1. Windows 10/11
2. Python 3.10 or newer (Add Python to PATH during installation)
3. Ollama for Windows
4. MiniCPM-V model downloaded in Ollama

ONE-TIME SETUP
1. Install Python from https://www.python.org/downloads/
2. Install Ollama from https://ollama.com/download
3. Open Command Prompt and run:
      ollama pull minicpm-v
4. Double-click INSTALL_DEPENDENCIES.bat
   (or simply double-click START_RENAMER.bat; it checks/install packages)

EVERYDAY USE
1. Ensure Ollama is running.
2. Double-click START_RENAMER.bat.
3. Click "Choose one image..." OR "Choose a folder..."
4. Optional: enable "Include subfolders" before choosing a folder.
5. Click "Analyze & prepare names".
6. Review bas1c_rename_preview.csv in the selected folder.
7. Return to the app and click "Execute approved renames".

IMPORTANT SAFETY NOTES
- Analysis does not rename files.
- Actual renaming requires a separate confirmation.
- Existing destination names are protected; no overwriting.
- Failed images remain unchanged.
- Keep a backup of important assets before bulk renaming.
- Do not move/delete the JSON plan or CSV during an active operation.

MODEL
Default model is minicpm-v. If your Ollama model has a tag such as minicpm-v:latest,
the default name normally resolves to it. You can change the model field in the app.

PORTABILITY
This folder contains the app and BAT launchers. Python and Ollama are external
prerequisites and must be installed on each Windows PC. The MiniCPM-V model must
also be pulled on that PC. The model itself is not bundled because it is large.
