# app.py (FINAL WORKING VERSION)

from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash
from werkzeug.utils import secure_filename
import os
from pathlib import Path
import shutil 
from datetime import datetime
import time 

# --- File Categorization Map ---
FILE_CATEGORIES = {
    'Images': ('.png', '.jpg', '.jpeg', '.gif', '.svg'),
    'Documents': ('.pdf', '.docx', '.txt', '.pptx', '.xlsx'),
    'Videos': ('.mp4', '.mov', '.avi', '.mkv'),
    'Archives': ('.zip', '.rar', '.tar', '.gz'),
}

def get_category_folder(filename):
    """Determines the category folder based on the file extension."""
    if '.' in filename:
        extension = filename.rsplit('.', 1)[1].lower()
        for folder, extensions in FILE_CATEGORIES.items():
            if '.' + extension in extensions:
                return folder
    return 'Others'

# --- Configuration ---
BASE_DIR = Path(os.path.abspath(os.path.dirname(__file__)))
UPLOAD_PATH = BASE_DIR / 'uploads'

# Added 'yaml'/'yml' based on previous request
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'zip', 'mp4', 'docx', 'xlsx', 'yml', 'yaml'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_PATH.name 
app.secret_key = 'your_strong_secret_key_here_for_flash_messages' 

UPLOAD_PATH.mkdir(exist_ok=True)

# --- Helper Functions ---
def allowed_file(filename):
    """Checks if a file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def human_readable_size(size, decimal_places=2):
    """Converts bytes to human-readable format (KB, MB, GB)."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.{decimal_places}f} {unit}"
        size /= 1024.0
    return f"{size:.{decimal_places}f} TB"

# --- Routes ---

@app.route('/', defaults={'req_path': ''})
@app.route('/<path:req_path>')
def index(req_path):
    """Renders the main page, handling file and directory browsing."""
    
    abs_path = UPLOAD_PATH / req_path
    current_dir = req_path if req_path else '' # Defined early to prevent NameError
    
    # Security Check 1: Prevent going above the UPLOAD_PATH
    if not abs_path.resolve().is_relative_to(UPLOAD_PATH.resolve()):
        flash("Access Denied: Cannot access folders outside the main directory.", 'error')
        return redirect(url_for('index', req_path=current_dir))

    # Check if path exists
    if not abs_path.exists():
        flash(f"Error: Path '{req_path}' not found.", 'error')
        return redirect(url_for('index'))

    # If the path is a file, redirect to the download route
    if abs_path.is_file():
        return redirect(url_for('download_file', filename=req_path))

    # If it's a directory: list its contents
    if abs_path.is_dir():
        items = []
        try:
            for item in abs_path.iterdir():
                relative_url_path = Path(req_path) / item.name
                stats = item.stat() 

                items.append({
                    'name': item.name,
                    'is_dir': item.is_dir(),
                    'url': url_for('index', req_path=relative_url_path), 
                    'size_hr': human_readable_size(stats.st_size) if item.is_file() else '',
                    'modified_hr': datetime.fromtimestamp(stats.st_mtime).strftime('%Y-%m-%d %H:%M')
                })
            
            # Sort by directory first, then by name
            items.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))

        except Exception as e:
            flash(f"Error accessing directory: {e}", 'error')
            
        return render_template(
            'index.html', 
            items=items,
            current_dir=current_dir,
            upload_folder=UPLOAD_PATH.name
        )
    

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handles multiple file uploads and automatically organizes them."""
    
    # CORRECTED: Uses 'file' to match the index.html input name
    uploaded_files = request.files.getlist('file') 

    # Get path for redirecting back
    target_path = request.form.get('current_path', '') 

    if not uploaded_files or uploaded_files[0].filename == '':
        flash("No file(s) selected for upload.", 'warning')
        return redirect(url_for('index', req_path=target_path))
    
    success_count = 0
    
    for file in uploaded_files:
        if file.filename and allowed_file(file.filename):
            try:
                # 1. Determine the destination folder 
                destination_folder_name = get_category_folder(file.filename)
                
                # 2. Define the absolute path for the category folder
                category_path = UPLOAD_PATH / destination_folder_name 
                
                # 3. Create the category folder if it doesn't exist
                category_path.mkdir(exist_ok=True)
                
                # 4. Secure and save the file
                filename = secure_filename(file.filename)
                file.save(category_path / filename)
                success_count += 1
                
            except Exception as e:
                flash(f"Error uploading {file.filename}: {e}", 'error')
                
        else:
             flash(f"File type not allowed for {file.filename}.", 'error')

        
    if success_count > 0:
        flash(f"Successfully uploaded {success_count} file(s)!", 'success')
    
    return redirect(url_for('index', req_path=target_path))


@app.route('/download/<path:filename>')
def download_file(filename):
    """Handles file downloads."""
    secure_name = secure_filename(Path(filename).name)
    directory = UPLOAD_PATH / Path(filename).parent
    
    return send_from_directory(
        directory, 
        secure_name, 
        as_attachment=True
    )


@app.route('/delete/<path:filename>', methods=['POST'])
def delete_file(filename):
    """Handles file or folder deletion."""
    
    item_path = UPLOAD_PATH / filename
    parent_path = str(item_path.parent.relative_to(UPLOAD_PATH))
    if parent_path == '.': parent_path = ''

    try:
        if not item_path.resolve().is_relative_to(UPLOAD_PATH.resolve()):
            flash("Security Error: Cannot delete outside the designated folder.", 'error')
            return redirect(url_for('index', req_path=parent_path))

        if item_path.is_file():
            os.remove(item_path)
            flash(f"File '{item_path.name}' deleted successfully.", 'success')
        elif item_path.is_dir():
            shutil.rmtree(item_path) 
            flash(f"Folder '{item_path.name}' deleted successfully.", 'success')
            
    except Exception as e:
        flash(f"Error deleting '{item_path.name}': {e}", 'error')
        
    return redirect(url_for('index', req_path=parent_path))


@app.route('/create_folder', methods=['POST'])
def create_folder():
    """Handles creating a new folder."""
    
    folder_name = request.form.get('folder_name')
    target_path = request.form.get('current_path', '')
    
    if not folder_name:
        flash("Folder name cannot be empty.", 'warning')
        return redirect(url_for('index', req_path=target_path))
    
    safe_folder_name = secure_filename(folder_name)
    new_folder_path = UPLOAD_PATH / target_path / safe_folder_name
    
    try:
        if not (UPLOAD_PATH / target_path).resolve().is_relative_to(UPLOAD_PATH.resolve()):
            flash("Security Error: Cannot create folder in a restricted location.", 'error')
            return redirect(url_for('index', req_path=target_path))
        
        new_folder_path.mkdir(exist_ok=False)
        flash(f"Folder '{safe_folder_name}' created successfully.", 'success')
    except FileExistsError:
        flash(f"Error: Folder '{safe_folder_name}' already exists.", 'error')
    except Exception as e:
        flash(f"Error creating folder: {e}", 'error')
        
    return redirect(url_for('index', req_path=target_path))


# --- Run the application ---
if __name__ == '__main__':
    app.run(debug=True)