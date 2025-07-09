#!/usr/bin/env python3
"""
GitHub repository storage for tracking data.
Commits tracking files back to the repository for persistence.
"""

import os
import json
import subprocess
from datetime import datetime

def commit_tracking_files_to_github():
    """Commit tracking files back to GitHub repository"""
    try:
        # Configure git for GitHub Actions
        subprocess.run(['git', 'config', 'user.name', 'GitHub Actions'], check=True)
        subprocess.run(['git', 'config', 'user.email', 'actions@github.com'], check=True)
        
        # Add tracking files
        files_to_commit = [
            'channel_tracking.json',
            'processed_messages.json', 
            'last_update.json'
        ]
        
        files_added = []
        for file in files_to_commit:
            if os.path.exists(file):
                subprocess.run(['git', 'add', file], check=True)
                files_added.append(file)
        
        if not files_added:
            print("📝 No tracking files to commit")
            return
        
        # Check if there are changes to commit
        result = subprocess.run(['git', 'diff', '--cached', '--exit-code'], capture_output=True)
        if result.returncode == 0:
            print("📝 No changes to tracking files")
            return
        
        # Commit with timestamp
        commit_message = f"Update tracking data - {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}"
        subprocess.run(['git', 'commit', '-m', commit_message], check=True)
        
        # Push to repository
        subprocess.run(['git', 'push'], check=True)
        
        print(f"✅ Committed tracking files to GitHub: {', '.join(files_added)}")
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Error committing to GitHub: {e}")
        print("This might be due to missing GitHub token or permissions")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

def setup_github_token():
    """Setup GitHub token for authentication"""
    github_token = os.getenv('GITHUB_TOKEN')
    if not github_token:
        print("⚠️  GITHUB_TOKEN not found - commits may fail")
        return False
    
    # Set up authentication for HTTPS
    auth_url = f"https://x-access-token:{github_token}@github.com/"
    
    try:
        # Get current remote URL
        result = subprocess.run(['git', 'remote', 'get-url', 'origin'], 
                              capture_output=True, text=True, check=True)
        current_url = result.stdout.strip()
        
        # Replace with authenticated URL if needed
        if not current_url.startswith('https://x-access-token:'):
            if current_url.startswith('https://github.com/'):
                new_url = current_url.replace('https://github.com/', auth_url)
                subprocess.run(['git', 'remote', 'set-url', 'origin', new_url], check=True)
                print("✅ GitHub authentication configured")
        
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error setting up GitHub authentication: {e}")
        return False

if __name__ == "__main__":
    setup_github_token()
    commit_tracking_files_to_github() 