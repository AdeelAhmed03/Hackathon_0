# File System Access Skill

## Purpose
Provides safe and controlled access to the file system for reading and writing operations.

## Capabilities
- Read files from any directory in the project
- Write files to designated data directories
- Move files between status directories
- List directory contents
- Check file existence

## Security Restrictions
- Cannot access files outside the project directory
- Cannot execute system commands
- Cannot modify skill or agent definition files
- All operations logged for audit purposes

## Usage
```
read_file: path/to/file
write_file: path/to/file content
move_file: from/path to/path
list_dir: directory/path
```