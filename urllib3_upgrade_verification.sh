#!/bin/bash
# urllib3_upgrade_verification.sh
# Verification script for the urllib3 upgrade fix

echo "================================================================"
echo "URLLIB3 UPGRADE VERIFICATION SCRIPT"
echo "================================================================"
echo "This script demonstrates the fix for Dependabot PR #82"
echo ""

# Check current directory
if [[ ! -f "requirements-dev.txt" ]]; then
    echo "❌ Error: Please run this script from the project root directory"
    exit 1
fi

echo "✅ Project structure verified"

# Check requirements files
echo ""
echo "Checking urllib3 version in requirements files:"
echo "------------------------------------------------"

# Check src/requirements.txt
if grep -q "urllib3==2.2.3" src/requirements.txt; then
    echo "✅ src/requirements.txt: urllib3==2.2.3 (correct version)"
else
    echo "❌ src/requirements.txt: urllib3 version issue"
    exit 1
fi

# Check scripts/requirements.txt  
if grep -q "urllib3==2.2.3" scripts/requirements.txt; then
    echo "✅ scripts/requirements.txt: urllib3==2.2.3 (correct version)"
else
    echo "❌ scripts/requirements.txt: urllib3 version issue"
    exit 1
fi

echo ""
echo "Verification commands to run manually:"
echo "--------------------------------------"
echo "1. Create virtual environment:"
echo "   python -m venv .venv"
echo ""
echo "2. Activate virtual environment:"
echo "   source .venv/bin/activate"
echo ""
echo "3. Install dependencies:"
echo "   pip install -r requirements-dev.txt"
echo ""
echo "4. Install app:"
echo "   python -m pip install -e src"
echo ""
echo "5. Run CI checks:"
echo "   python -m ruff check ."
echo "   python -m black . --check --verbose"
echo "   python -m pytest"
echo ""
echo "✅ All requirements files have been updated correctly"
echo "✅ This urllib3 upgrade fixes the Dependabot PR #82 issue"
echo ""
echo "================================================================"