import os
import shutil
import argparse
import csv
import hashlib
import time
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Define file categories and their extensions
CATEGORIES = {
    "Images": [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".svg", ".heic"],
    "Documents": [".pdf", ".docx", ".doc", ".txt", ".rtf", ".xlsx", ".xls", ".pptx", ".ppt", ".md", ".odt"],
    "Audio": [".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma"],
    "Videos": [".mp4", ".mov", ".avi", ".mkv", ".flv", ".wmv", ".mpeg", ".webm", ".3gp"],
    "Code": [".py", ".js", ".html", ".css", ".java", ".cpp", ".c", ".php", ".json", ".xml", ".yml", ".sql"],
    "Archives": [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"],
    "Executables": [".exe", ".msi", ".dmg", ".pkg", ".app", ".bat", ".sh", ".deb", ".rpm"],
    "Design": [".psd", ".ai", ".xd", ".sketch", ".fig", ".indd"],
    "Data": [".csv", ".tsv", ".db", ".sqlite", ".parquet", ".feather"],
    "Others": []  # Default category for unrecognized types
}

# ASCII art for visual appeal
BANNER = r"""
  ___ _ _        __          _                         
 | __(_) |_ ___ / _|___ _ __| |_ _ _ __ _ _ __ _ __ ___ 
 | _|| |  _/ -_)  _/ _ \ '_ \  _| '_/ _` | '_ \ '_ ` _ \
 |_| |_|\__\___|_| \___/ .__/\__|_| \__,_| .__/|_| |_| |
                       |_|               |_|           
"""

def create_category_folders(target_path):
    """Create category folders in the target directory"""
    for category in CATEGORIES:
        folder_path = target_path / category
        folder_path.mkdir(exist_ok=True)

def get_file_hash(file_path):
    """Generate MD5 hash for a file"""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def organize_files(target_path, log_file):
    """
    Organize files in the target directory into categorized folders
    Returns: Tuple of (total files moved, files moved per category, space saved)
    """
    create_category_folders(target_path)
    
    # Track statistics
    file_count = 0
    category_counts = defaultdict(int)
    original_size = 0
    duplicate_count = 0
    seen_hashes = {}
    
    # Create a log file if it doesn't exist
    if not log_file.exists():
        with open(log_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "original_path", "destination", "file_hash", "file_size"])
    
    # Process all items in the target directory
    for item in target_path.iterdir():
        # Skip directories, hidden files, and the log file itself
        if (item.is_dir() or 
            item.name.startswith('.') or 
            item.name == "organization_log.csv" or
            item.name == log_file.name):
            continue
            
        file_size = item.stat().st_size
        original_size += file_size
        file_hash = get_file_hash(item)
        moved = False
        
        # Check for duplicates
        if file_hash in seen_hashes:
            duplicate_count += 1
            print(f"⚠️ Duplicate found: {item.name} (same as {seen_hashes[file_hash]})")
            # We'll still process duplicates but note them in log
        else:
            seen_hashes[file_hash] = item.name
        
        # Find matching category
        file_extension = item.suffix.lower()
        for category, extensions in CATEGORIES.items():
            if file_extension in extensions:
                destination = target_path / category / item.name
                
                try:
                    shutil.move(str(item), str(destination))
                    print(f"✓ Moved {item.name} to {category}/")
                    file_count += 1
                    category_counts[category] += 1
                    
                    # Log the move
                    with open(log_file, "a", newline="") as f:
                        writer = csv.writer(f)
                        writer.writerow([
                            datetime.now().isoformat(),
                            str(item),
                            str(destination),
                            file_hash,
                            file_size
                        ])
                    
                    moved = True
                    break
                except Exception as e:
                    print(f"⚠️ Error moving {item.name}: {str(e)}")
                    moved = True  # Mark as moved to avoid duplicate handling
                    break
        
        # Handle unrecognized file types
        if not moved:
            destination = target_path / "Others" / item.name
            try:
                shutil.move(str(item), str(destination))
                print(f"✓ Moved {item.name} to Others/")
                file_count += 1
                category_counts["Others"] += 1
                
                # Log the move
                with open(log_file, "a", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        datetime.now().isoformat(),
                        str(item),
                        str(destination),
                        file_hash,
                        file_size
                    ])
            except Exception as e:
                print(f"⚠️ Error moving {item.name}: {str(e)}")
    
    # Calculate space saved (only unique files)
    unique_files_size = sum(size for hash, size in seen_hashes.values())
    space_saved = original_size - unique_files_size
    
    return file_count, dict(category_counts), duplicate_count, space_saved

def undo_organization(log_file):
    """Undo the last organization based on the log file"""
    if not log_file.exists():
        print("❌ No organization log found - nothing to undo!")
        return 0
    
    # Read all log entries
    with open(log_file, "r", newline="") as f:
        reader = csv.DictReader(f)
        moves = list(reader)
    
    if not moves:
        print("ℹ️ Organization log is empty - nothing to undo!")
        return 0
    
    # Group moves by timestamp (each organization session has a unique timestamp)
    sessions = defaultdict(list)
    for move in moves:
        sessions[move['timestamp']].append(move)
    
    # Get the latest session
    latest_timestamp = max(sessions.keys())
    latest_moves = sessions[latest_timestamp]
    
    # Undo each move in the latest session
    restored_count = 0
    for move in latest_moves:
        src = Path(move['destination'])
        dest = Path(move['original_path'])
        
        # Ensure parent directory exists
        dest.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            shutil.move(str(src), str(dest))
            print(f"↩️ Restored {src.name} to original location")
            restored_count += 1
        except Exception as e:
            print(f"⚠️ Error restoring {src.name}: {str(e)}")
    
    return restored_count

def print_summary(file_count, category_counts, duplicate_count, space_saved, duration):
    """Print a formatted summary of the organization results"""
    print("\n" + "="*50)
    print("✅ ORGANIZATION SUMMARY")
    print("="*50)
    
    print(f"\n📊 Total files organized: {file_count}")
    print(f"⏱️  Time taken: {duration:.2f} seconds")
    
    if duplicate_count > 0:
        print(f"\n⚠️  Duplicate files found: {duplicate_count}")
    
    if space_saved > 0:
        print(f"\n💾 Space saved by removing duplicates: {space_saved/1024/1024:.2f} MB")
    
    print("\n📂 Files per category:")
    for category, count in category_counts.items():
        if count > 0:
            print(f"  {category + ':':<12} {count} files")
    
    if file_count == 0:
        print("\nℹ️ No files needed organization - everything is already sorted!")
    
    print("\n" + "="*50)

def main():
    """Main function to handle command-line arguments and execution"""
    print(BANNER)
    
    parser = argparse.ArgumentParser(
        description="📂 Auto File Organizer - Sort files into categorized folders",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--target", 
        default="Downloads",
        help="Folder to organize (default: Downloads)\nExamples:\n  --target Desktop\n  --target 'C:/My Folder'"
    )
    parser.add_argument(
        "--undo", 
        action="store_true",
        help="Undo the last organization operation"
    )
    parser.add_argument(
        "--log",
        default="organization_log.csv",
        help="Log file path (default: organization_log.csv)"
    )
    
    args = parser.parse_args()
    
    # Set up paths
    target_path = Path(args.target).expanduser()
    log_path = Path(args.log)
    
    # Handle special "Downloads" default case
    if args.target == "Downloads":
        target_path = Path.home() / "Downloads"
    
    # Verify target exists
    if not target_path.exists():
        print(f"❌ Error: Target folder '{target_path}' doesn't exist!")
        return
    
    # Handle undo operation
    if args.undo:
        print(f"\n↩️ Attempting to undo last organization for: {target_path}")
        start_time = time.time()
        restored_count = undo_organization(log_path)
        duration = time.time() - start_time
        
        print("\n" + "="*50)
        if restored_count > 0:
            print(f"✅ Successfully restored {restored_count} files in {duration:.2f} seconds!")
        else:
            print("ℹ️ No files were restored")
        print("="*50)
        return
    
    # Perform organization
    print(f"\n🚀 Starting organization of: {target_path}")
    start_time = time.time()
    total_files, category_counts, duplicate_count, space_saved = organize_files(target_path, log_path)
    duration = time.time() - start_time
    
    # Print summary
    print_summary(total_files, category_counts, duplicate_count, space_saved, duration)

if __name__ == "__main__":
    main()