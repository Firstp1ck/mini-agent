#!/bin/bash
#
# release.sh
# ==========
#
# mini-agent - Release Script
#
# PURPOSE:
#   Creates a git tag and pushes it to trigger the GitHub Actions release workflow
#   (.github/workflows/release-binaries.yml). Updates the version in pyproject.toml
#   and creates a git tag that triggers CI builds (PyInstaller artifacts).
#
# WHAT IT DOES:
#   - Validates version format (vX.X.X)
#   - Checks for existing tags/releases and optionally deletes them
#   - Updates the version number in pyproject.toml
#   - Regenerates uv.lock
#   - Commits and pushes version changes
#   - Creates and pushes a git tag
#   - Provides status updates and links to monitor the workflow
#
# USAGE:
#   ./dev/release.sh [version]
#
# EXAMPLES:
#   ./dev/release.sh 0.1.0
#   ./dev/release.sh 1.2.3
#   ./dev/release.sh    (will prompt for version)
#
# NOTE:
#   - Version should be in format X.X.X (without 'v' prefix)
#   - The 'v' prefix will be added automatically
#   - If no version is provided, the script will prompt for input
#
# REQUIREMENTS:
#   - Git
#   - GitHub CLI (gh) - optional but recommended for release management
#   - uv - optional for lock file regeneration
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored messages
print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Ensure local branch HEAD is available on remote before tagging.
# This prevents creating a release tag for commits that are not pushed yet.
ensure_branch_head_on_remote() {
    local branch="$1"
    local local_head remote_head

    while true; do
        local_head=$(git rev-parse HEAD)
        remote_head=$(git ls-remote origin "refs/heads/$branch" | awk '{print $1}')

        if [ -n "$remote_head" ] && [ "$remote_head" = "$local_head" ]; then
            print_success "Remote branch $branch is up to date with local HEAD"
            return 0
        fi

        print_warning "Remote branch $branch is not at local HEAD yet"
        echo "Local HEAD : $local_head"
        echo "Remote HEAD: ${remote_head:-<not found>}"
        read -p "Push manually now and press Enter to re-check (or type 'q' to cancel): " retry_input
        if [[ "$retry_input" =~ ^[Qq]$ ]]; then
            print_info "Release cancelled"
            return 1
        fi
    done
}

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check for required tools
print_info "Checking for required tools..."

if ! command_exists git; then
    print_error "git is not installed. Please install it first."
    exit 1
fi
print_success "git is installed"

# Check for GitHub CLI (optional but recommended for release deletion)
GH_AVAILABLE=false
if command_exists gh; then
    GH_AVAILABLE=true
    print_success "GitHub CLI (gh) is installed"
else
    print_warning "GitHub CLI (gh) is not installed (optional, but recommended for release management)"
fi

# Get version from argument or prompt user
if [ $# -eq 0 ]; then
    print_info "No version argument provided"
    echo ""
    echo "Please enter the version number (format: X.X.X)"
    echo "Examples: 0.1.0, 1.2.3, 2.0.0"
    echo "Note: The 'v' prefix will be added automatically"
    echo ""
    read -p "Version: " VERSION_INPUT
    if [ -z "$VERSION_INPUT" ]; then
        print_error "Version cannot be empty"
        exit 1
    fi
    VERSION="$VERSION_INPUT"
else
    VERSION="$1"
fi

# Remove 'v' prefix if present (we'll add it back)
VERSION="${VERSION#v}"

# Validate version format (should be X.X.X)
if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    print_error "Invalid version format: $VERSION"
    echo "Version should be in format: X.X.X (without 'v' prefix)"
    echo "Examples: 0.1.0, 1.2.3, 2.0.0"
    exit 1
fi

# Add 'v' prefix
VERSION="v$VERSION"

print_success "Version format is valid: $VERSION"

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    print_error "Not in a git repository"
    exit 1
fi

# Check if there are uncommitted changes (only tracked files, ignore untracked)
if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
    TRACKED_CHANGES=$(git status --porcelain 2>/dev/null | grep -v '^??' || true)
    if [ -n "$TRACKED_CHANGES" ]; then
        print_warning "You have uncommitted changes in tracked files"
        read -p "Do you want to continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "Release cancelled"
            exit 0
        fi
    fi
fi

# Check if remote is configured
if ! git remote get-url origin > /dev/null 2>&1; then
    print_error "No remote 'origin' configured"
    exit 1
fi

# Extract repository name from remote URL for GitHub API
REMOTE_URL=$(git remote get-url origin)
REPO_NAME=""
if [[ "$REMOTE_URL" =~ github\.com[:/]([^/]+/[^/]+) ]]; then
    REPO_NAME="${BASH_REMATCH[1]}"
    REPO_NAME="${REPO_NAME%.git}"
fi

# Check if release already exists on GitHub
RELEASE_EXISTS=false
if [ "$GH_AVAILABLE" = true ] && [ -n "$REPO_NAME" ]; then
    print_info "Checking if release $VERSION already exists on GitHub..."
    if gh release view "$VERSION" --repo "$REPO_NAME" >/dev/null 2>&1; then
        RELEASE_EXISTS=true
        print_warning "Release $VERSION already exists on GitHub"
    else
        print_info "Release $VERSION does not exist on GitHub"
    fi
fi

# Check if tag already exists (local or remote)
TAG_EXISTS_LOCAL=false
TAG_EXISTS_REMOTE=false

if git rev-parse "$VERSION" >/dev/null 2>&1; then
    TAG_EXISTS_LOCAL=true
fi

if git ls-remote --tags origin 2>&1 | grep -q "refs/tags/$VERSION"; then
    TAG_EXISTS_REMOTE=true
fi

# If release or tag exists, delete them
if [ "$RELEASE_EXISTS" = true ] || [ "$TAG_EXISTS_LOCAL" = true ] || [ "$TAG_EXISTS_REMOTE" = true ]; then
    if [ "$RELEASE_EXISTS" = true ]; then
        print_warning "Release $VERSION will be deleted and recreated"
    fi
    if [ "$TAG_EXISTS_LOCAL" = true ] || [ "$TAG_EXISTS_REMOTE" = true ]; then
        print_warning "Tag $VERSION will be deleted and recreated"
    fi

    if ! read -p "Do you want to delete and recreate? (y/N) " -n 1 -r; then
        echo
        print_info "Release cancelled"
        exit 0
    fi
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Release cancelled"
        exit 0
    fi
    
    # Delete GitHub release if it exists
    if [ "$RELEASE_EXISTS" = true ] && [ "$GH_AVAILABLE" = true ]; then
        print_info "Deleting existing GitHub release..."
        if gh release delete "$VERSION" --repo "$REPO_NAME" --yes >/dev/null 2>&1; then
            print_success "GitHub release deleted"
        else
            print_error "Failed to delete GitHub release"
            print_warning "You may need to delete it manually from GitHub"
        fi
    elif [ "$RELEASE_EXISTS" = true ]; then
        print_warning "Cannot delete GitHub release automatically (gh CLI not available)"
        print_warning "Please delete it manually from: https://github.com/$REPO_NAME/releases/tag/$VERSION"
    fi
    
    # Delete remote tag if it exists
    if [ "$TAG_EXISTS_REMOTE" = true ]; then
        print_info "Deleting remote tag..."
        if git push origin ":refs/tags/$VERSION" >/dev/null 2>&1; then
            print_success "Remote tag deleted"
        else
            print_warning "Failed to delete remote tag (may not exist or already deleted)"
        fi
    fi
    
    # Delete local tag if it exists
    if [ "$TAG_EXISTS_LOCAL" = true ]; then
        print_info "Deleting local tag..."
        git tag -d "$VERSION" >/dev/null 2>&1 || true
        print_success "Local tag deleted"
    fi
fi

# Get current branch
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
print_info "Current branch: $CURRENT_BRANCH"

# Check if we're on main/master branch
if [[ "$CURRENT_BRANCH" != "main" && "$CURRENT_BRANCH" != "master" ]]; then
    print_warning "You're not on main/master branch"
    read -p "Do you want to continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Release cancelled"
        exit 0
    fi
fi

# Verify repository name was extracted successfully
if [ -z "$REPO_NAME" ]; then
    print_error "Could not determine repository name from remote URL"
    exit 1
fi

print_info "Remote repository: $REPO_NAME"

# Extract version number without 'v' prefix (e.g., v0.1.0 -> 0.1.0)
VERSION_NUMBER="${VERSION#v}"

# Get script directory and project root (one level up from dev/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# --- Release notes ---
RELEASE_NOTES_FILE="$PROJECT_ROOT/dev/Release-docs/RELEASE_${VERSION}.md"
RELEASE_NOTES_REL="dev/Release-docs/RELEASE_${VERSION}.md"

if [ -f "$RELEASE_NOTES_FILE" ]; then
    print_success "Release notes found: $RELEASE_NOTES_REL"
else
    echo ""
    echo "============================================================"
    print_warning "Release notes file not found: $RELEASE_NOTES_REL"
    echo "============================================================"
    echo ""
    print_info "Please switch to Cursor and run the command:"
    echo ""
    echo -e "    ${GREEN}/release-new${NC}"
    echo ""
    print_info "This will generate the release notes file for $VERSION."
    echo ""
    echo "------------------------------------------------------------"
    read -p "Press Enter once you have created the release notes... "
    echo ""

    # Verify the file was created
    if [ ! -f "$RELEASE_NOTES_FILE" ]; then
        print_error "Release notes file still not found: $RELEASE_NOTES_REL"
        print_error "Cannot proceed without release notes. Aborting."
        exit 1
    fi
    print_success "Release notes found: $RELEASE_NOTES_REL"
fi

# Show release notes preview
echo ""
print_info "Release notes preview:"
echo "------------------------------------------------------------"
head -20 "$RELEASE_NOTES_FILE"
if [ "$(wc -l < "$RELEASE_NOTES_FILE")" -gt 20 ]; then
    echo "  ... (truncated)"
fi
echo "------------------------------------------------------------"
echo ""

# Remind documentation update commands in Cursor
print_info "Before finalizing the release documentation:"
echo -e "    ${GREEN}/readme-update${NC}  -> updates README.md"
echo ""

# Commit and push release documentation if new or modified. This runs after the
# README reminder so /readme-update changes are included before the tag triggers
# the release workflow.
README_FILE="$PROJECT_ROOT/README.md"
RELEASE_DOCS_CHANGED=false
RELEASE_DOC_FILES=("$RELEASE_NOTES_FILE" "$README_FILE")

for doc_file in "${RELEASE_DOC_FILES[@]}"; do
    if [ ! -f "$doc_file" ]; then
        continue
    fi
    if ! git ls-files --error-unmatch "$doc_file" >/dev/null 2>&1; then
        RELEASE_DOCS_CHANGED=true
    elif [ -n "$(git diff -- "$doc_file" 2>/dev/null)" ]; then
        RELEASE_DOCS_CHANGED=true
    elif [ -n "$(git diff --cached -- "$doc_file" 2>/dev/null)" ]; then
        RELEASE_DOCS_CHANGED=true
    fi
done

if [ "$RELEASE_DOCS_CHANGED" = true ]; then
    read -p "Commit and push release documentation? (Y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        print_info "Staging release documentation..."
        for doc_file in "${RELEASE_DOC_FILES[@]}"; do
            [ -f "$doc_file" ] && git add "$doc_file"
        done

        print_info "Committing release documentation..."
        if git commit -m "docs: update release documentation for $VERSION" >/dev/null 2>&1; then
            print_success "Release documentation committed"
        else
            print_error "Failed to commit release documentation"
            exit 1
        fi

        print_info "Pushing release documentation to remote..."
        if git push origin "$CURRENT_BRANCH" >/dev/null 2>&1; then
            print_success "Release documentation pushed successfully"
        else
            print_error "Failed to push release documentation"
            echo "You can push manually with: git push origin $CURRENT_BRANCH"
            exit 1
        fi
    else
        print_warning "Skipped committing release documentation"
        print_warning "Make sure release documentation is pushed before the workflow runs!"
    fi
else
    print_info "Release documentation already committed — no changes detected"
fi

# Update version in pyproject.toml
print_info "Updating version in pyproject.toml..."
PYPROJECT_TOML="$PROJECT_ROOT/pyproject.toml"
if [ -f "$PYPROJECT_TOML" ]; then
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s/^version = \"[^\"]*\"/version = \"$VERSION_NUMBER\"/" "$PYPROJECT_TOML"
    else
        sed -i "s/^version = \"[^\"]*\"/version = \"$VERSION_NUMBER\"/" "$PYPROJECT_TOML"
    fi
    print_success "Updated version in pyproject.toml to $VERSION_NUMBER"
else
    print_error "File not found: $PYPROJECT_TOML"
    exit 1
fi

# Regenerate uv.lock
UV_LOCK="$PROJECT_ROOT/uv.lock"
if [ -f "$UV_LOCK" ]; then
    print_info "Regenerating uv.lock..."
    if command_exists uv; then
        (cd "$PROJECT_ROOT" && uv lock --no-upgrade --system-certs >/dev/null 2>&1 || uv lock --system-certs >/dev/null 2>&1)
        print_success "Regenerated uv.lock"
    else
        print_warning "uv not found, skipping uv.lock regeneration"
    fi
fi

# Stage modified files
print_info "Staging version changes..."
git add "$PYPROJECT_TOML" 2>/dev/null || true
[ -f "$UV_LOCK" ] && git add "$UV_LOCK" 2>/dev/null || true

# Check if there are staged changes to commit
if [ -z "$(git diff --cached --name-only 2>/dev/null)" ]; then
    print_warning "No changes detected after version update"
    print_info "Version may already be at $VERSION_NUMBER - continuing to tag creation"
else
    # Commit the changes
    print_info "Committing version changes..."
    if git commit -m "chore: bump version to $VERSION_NUMBER" >/dev/null 2>&1; then
        print_success "Version changes committed"
    else
        print_error "Failed to commit version changes"
        exit 1
    fi
    
    # Push the commit
    print_info "Pushing version commit to remote..."
    if git push origin "$CURRENT_BRANCH" >/dev/null 2>&1; then
        print_success "Version commit pushed successfully"
    else
        print_warning "Failed to push version commit automatically"
        echo "You can push it manually with: git push origin $CURRENT_BRANCH"
        if ! ensure_branch_head_on_remote "$CURRENT_BRANCH"; then
            exit 1
        fi
    fi
fi

# If no version commit was needed, still ensure the current HEAD is reachable on remote
# before creating and pushing a tag that triggers the release workflow.
if ! ensure_branch_head_on_remote "$CURRENT_BRANCH"; then
    exit 1
fi

# Confirm release
echo ""
print_warning "You are about to create and push tag: $VERSION"
print_warning "This will trigger the GitHub Actions release workflow"
echo ""
if ! read -p "Are you sure you want to continue? (y/N) " -n 1 -r; then
    echo
    print_info "Release cancelled"
    exit 0
fi
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_info "Release cancelled"
    exit 0
fi

# Create the tag
print_info "Creating tag $VERSION..."
git tag -a "$VERSION" -m "Release $VERSION"
print_success "Tag created locally"

# Push the tag
print_info "Pushing tag to remote..."
if git push origin "$VERSION"; then
    print_success "Tag pushed successfully"
else
    print_error "Failed to push tag"
    echo "You can push it manually with: git push origin $VERSION"
    exit 1
fi

# Print success message
echo ""
print_success "=========================================="
print_success "Release $VERSION triggered successfully!"
print_success "=========================================="
echo ""
print_info "The GitHub Actions workflow has been triggered"
print_info "You can monitor the progress at:"
echo "  https://github.com/$REPO_NAME/actions"
echo ""
print_info "Once the workflow completes, the release will be available at:"
echo "  https://github.com/$REPO_NAME/releases/tag/$VERSION"
echo ""
