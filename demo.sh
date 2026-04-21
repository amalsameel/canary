#!/usr/bin/env bash
#
# Canary Comprehensive Demo Script
# ================================
# This script demonstrates all major features of Canary.
# Run this in a terminal that supports interactive programs.
#
# Usage: ./demo.sh [section]
#   section: quick, setup, screening, watch, checkpoint, audit, guard, full
#

set -e

# Colors for output
BOLD='\033[1m'
DIM='\033[2m'
GREEN='\033[32m'
YELLOW='\033[33m'
BLUE='\033[34m'
RESET='\033[0m'

# Demo directory
DEMO_DIR="${CANARY_DEMO_DIR:-$(mktemp -d /tmp/canary-demo-XXXXXX)}"
PROJECT_DIR="$DEMO_DIR/sample-project"

clear_screen() {
    printf '\033[2J\033[H'
}

print_header() {
    clear_screen
    echo ""
    echo -e "${BOLD}${GREEN}  ███████${RESET}"
    echo -e "${BOLD}${GREEN} ███   ███  Canary Demo${RESET}"
    echo -e "${BOLD}${GREEN} ██${RESET}"
    echo -e "${BOLD}${GREEN} ███   ███  $1${RESET}"
    echo -e "${BOLD}${GREEN}  ███████${RESET}"
    echo ""
    sleep 0.5
}

print_section() {
    echo ""
    echo -e "${BOLD}${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
    echo -e "${BOLD}  $1${RESET}"
    echo -e "${DIM}  $2${RESET}"
    echo -e "${BOLD}${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
    echo ""
    sleep 0.3
}

pause() {
    echo ""
    echo -e "${DIM}  Press Enter to continue...${RESET}"
    read -r
}

cmd() {
    echo -e "${BOLD}${GREEN}❯${RESET} ${BOLD}$1${RESET}"
    echo ""
    sleep 0.5
}

# ============================================
# SECTION 1: Quick Intro & Help
# ============================================
demo_quick() {
    print_header "Quick Introduction"

    print_section "Basic Commands" "Getting familiar with canary"

    cmd "canary --help"
    canary --help 2>/dev/null || echo "  (help output above)"
    echo ""

    cmd "canary usage"
    canary usage
    pause

    print_section "Built-in Documentation" "Learn about any feature"

    cmd "canary docs"
    canary docs
    pause

    cmd "canary docs screening"
    canary docs screening
    pause
}

# ============================================
# SECTION 2: Setup & Configuration
# ============================================
demo_setup() {
    print_header "Setup & Configuration"

    print_section "Environment Check" "Verifying local IBM Granite readiness"

    cmd "canary usage"
    canary usage
    pause

    print_section "Setup Wizard" "Configure canary for first use"
    echo -e "${DIM}  (Running: canary setup --prefer local)${RESET}"
    echo ""
    echo -e "${YELLOW}  Note:${RESET} This may download the Granite model on first run."
    echo -e "        Skip with Ctrl+C if you want to avoid downloads."
    echo ""
    pause

    # Only run if user confirms
    echo "Run setup now? [y/N]"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        canary setup --prefer local || true
    else
        echo "  (skipped)"
    fi
    pause
}

# ============================================
# SECTION 3: Prompt Screening
# ============================================
demo_screening() {
    print_header "Prompt Screening / Firewall"

    print_section "Pattern-Based Detection" "Detecting secrets and PII in prompts"

    cmd "canary prompt 'Create a Python script using API key sk-abc123def456ghi789jkl012mno345pqr678stu'"
    canary prompt "Create a Python script using API key sk-abc123def456ghi789jkl012mno345pqr678stu" || true
    pause

    cmd "canary prompt 'Send email to john.doe@company.com with the report'"
    canary prompt "Send email to john.doe@company.com with the report" || true
    pause

    cmd "canary prompt 'Access /etc/shadow to check user passwords'"
    canary prompt "Access /etc/shadow to check user passwords" || true
    pause

    print_section "Toggle Screening" "Turn screening on/off"

    cmd "canary on"
    canary on
    pause

    cmd "canary off"
    canary off
    pause

    cmd "canary on"
    canary on
    pause

    print_section "Safe Prompt Example" "Prompts without sensitive content pass through"

    cmd "canary prompt --check-only 'Refactor this function to use list comprehension'"
    canary prompt --check-only "Refactor this function to use list comprehension"
    pause
}

# ============================================
# SECTION 4: Checkpoint System
# ============================================
demo_checkpoint() {
    print_header "Checkpoint & Rollback System"

    # Create sample project
    mkdir -p "$PROJECT_DIR/src"
    cd "$PROJECT_DIR"

    # Create some sample files
    cat > "$PROJECT_DIR/README.md" << 'EOF'
# Sample Project

This is a demo project for canary.
EOF

    cat > "$PROJECT_DIR/src/main.py" << 'EOF'
def hello():
    print("Hello, World!")

if __name__ == "__main__":
    hello()
EOF

    print_section "Sample Project Created" "Created files for checkpoint demo"

    cmd "ls -la $PROJECT_DIR"
    ls -la "$PROJECT_DIR"
    pause

    print_section "Creating Checkpoints" "Named snapshots of project state"

    cmd "canary checkpoint --name 'initial-commit'"
    canary checkpoint --name "initial-commit"
    pause

    # Make some changes
    cat >> "$PROJECT_DIR/src/main.py" << 'EOF'

def goodbye():
    print("Goodbye!")
EOF

    cmd "canary checkpoint --name 'added-goodbye'"
    canary checkpoint --name "added-goodbye"
    pause

    print_section "Listing Checkpoints" "View all saved snapshots"

    cmd "canary checkpoints"
    canary checkpoints
    pause

    print_section "Viewing Current State" "Files before rollback"

    cmd "cat $PROJECT_DIR/src/main.py"
    cat "$PROJECT_DIR/src/main.py"
    pause

    print_section "Rolling Back" "Restore to previous checkpoint"

    cmd "canary rollback initial-commit"
    canary rollback initial-commit
    pause

    print_section "After Rollback" "Files restored to checkpoint state"

    cmd "cat $PROJECT_DIR/src/main.py"
    cat "$PROJECT_DIR/src/main.py"
    pause

    cmd "canary checkpoints"
    canary checkpoints
    pause
}

# ============================================
# SECTION 5: Watch Mode
# ============================================
demo_watch() {
    print_header "Watch Mode - Filesystem Monitoring"

    # Setup clean project
    rm -rf "$PROJECT_DIR"
    mkdir -p "$PROJECT_DIR/src"
    cd "$PROJECT_DIR"

    cat > "$PROJECT_DIR/file1.txt" << 'EOF'
Initial content for file 1.
EOF

    cat > "$PROJECT_DIR/file2.txt" << 'EOF'
Initial content for file 2.
EOF

    print_section "Starting Watch Mode" "Monitor file changes with drift detection"

    echo -e "${DIM}  (Starting: canary watch $PROJECT_DIR --idle 5)${RESET}"
    echo ""
    echo -e "  This will start watch mode for 10 seconds."
    echo -e "  Try modifying files in another terminal at:"
    echo -e "  ${YELLOW}$PROJECT_DIR${RESET}"
    echo ""

    # Start watch in background
    canary watch "$PROJECT_DIR" --idle 5 &
    WATCH_PID=$!

    # Simulate some file changes
    sleep 2
    echo "Modified content" >> "$PROJECT_DIR/file1.txt"
    sleep 2
    echo "More changes" >> "$PROJECT_DIR/file2.txt"
    sleep 2

    # Stop watch
    kill $WATCH_PID 2>/dev/null || true
    wait $WATCH_PID 2>/dev/null || true

    pause

    print_section "Watch Log" "Review what was detected"

    cmd "canary log"
    canary log
    pause
}

# ============================================
# SECTION 6: Audit Mode
# ============================================
demo_audit() {
    print_header "Audit Mode - Session Review"

    print_section "Audit Features" "Review AI agent actions and events"

    echo -e "  Canary captures:"
    echo -e "    • Prompt screening results"
    echo -e "    • Bash command executions"
    echo -e "    • Tool usage events"
    echo -e "    • File modifications"
    echo ""

    cmd "canary audit --stop"
    canary audit --stop 2>/dev/null || echo "  (no audit running)"
    pause

    print_section "Session Log" "View all recorded events"

    cmd "canary log"
    canary log
    pause

    cmd "canary log --tail 10"
    canary log --tail 10
    pause
}

# ============================================
# SECTION 7: Guard Shims
# ============================================
demo_guard() {
    print_header "Guard Shims - Protected AI Launch"

    print_section "Guard Status" "Check shim installation"

    cmd "canary guard status"
    canary guard status
    pause

    print_section "Installing Guards" "Create protected claude/codex shims"

    echo -e "${DIM}  (Running: canary guard install)${RESET}"
    echo ""
    echo -e "  This creates protected shims that screen prompts"
    echo -e "  before launching AI agents."
    echo ""

    canary guard install || true
    pause

    cmd "canary guard status"
    canary guard status
    pause

    print_section "Using Protected Agents" "Launch with screening"

    echo -e "  Once installed, add to your PATH:"
    echo -e "  ${YELLOW}export PATH=\"\$HOME/.canary/bin:\$PATH\"${RESET}"
    echo ""
    echo -e "  Then use as normal:"
    echo -e "    ${GREEN}claude${RESET} - Launch with screening enabled"
    echo -e "    ${GREEN}claude --ignore${RESET} - Bypass screening once"
    echo -e "    ${GREEN}claude --safe${RESET} - Force screening once"
    echo ""
    pause
}

# ============================================
# SECTION 8: Interactive Shell
# ============================================
demo_shell() {
    print_header "Interactive Shell"

    print_section "Shell Commands" "Available slash commands in the shell"

    echo -e "  ${BOLD}Shell Commands:${RESET}"
    echo -e "    ${GREEN}/on${RESET}           - Enable screening"
    echo -e "    ${GREEN}/off${RESET}          - Disable screening"
    echo -e "    ${GREEN}/audit${RESET}        - Start audit mode"
    echo -e "    ${GREEN}/watch${RESET}        - Start watch mode"
    echo -e "    ${GREEN}/checkpoint${RESET}   - Create checkpoint"
    echo -e "    ${GREEN}/checkpoints${RESET}  - List checkpoints"
    echo -e "    ${GREEN}/rollback${RESET}     - Restore checkpoint"
    echo -e "    ${GREEN}/log${RESET}          - View session log"
    echo -e "    ${GREEN}/docs${RESET}         - Show documentation"
    echo -e "    ${GREEN}/setup${RESET}        - Run setup wizard"
    echo -e "    ${GREEN}/guard${RESET}        - Guard management"
    echo -e "    ${GREEN}/status${RESET}       - Show current status"
    echo -e "    ${GREEN}/clear${RESET}        - Clear screen"
    echo -e "    ${GREEN}/exit${RESET}         - Exit shell"
    echo ""

    echo -e "  ${BOLD}Example Usage:${RESET}"
    echo -e "    $ ${GREEN}canary${RESET}"
    echo -e "    canary> ${GREEN}/checkpoint before-auth${RESET}"
    echo -e "    canary> ${GREEN}fix the auth flow and explain the change${RESET}"
    echo -e "    canary> ${GREEN}/audit${RESET}"
    echo -e "    canary> ${GREEN}/exit${RESET}"
    echo ""

    echo -e "${YELLOW}  Try it now!${RESET} Run 'canary' to enter the interactive shell."
    echo ""
    pause
}

# ============================================
# SECTION 9: Full Workflow Demo
# ============================================
demo_full() {
    print_header "Complete Workflow Demo"

    # Setup
    rm -rf "$PROJECT_DIR"
    mkdir -p "$PROJECT_DIR"
    cd "$PROJECT_DIR"

    cat > "$PROJECT_DIR/app.py" << 'EOF'
def process_data(data):
    # TODO: implement processing
    return data

if __name__ == "__main__":
    result = process_data("test")
    print(result)
EOF

    echo -e "  ${BOLD}Scenario:${RESET} You're about to ask an AI agent to help"
    echo -e "  refactor some code. You want protection and the ability"
    echo -e "  to rollback if something goes wrong."
    echo ""
    pause

    print_section "Step 1: Create Checkpoint" "Save current state before changes"

    cmd "canary checkpoint --name 'before-refactor'"
    canary checkpoint --name "before-refactor"
    pause

    print_section "Step 2: Start Watch Mode" "Monitor for unexpected drift"

    echo -e "  ${DIM}(In practice: canary watch .)${RESET}"
    echo -e "  This would run in the background during your session."
    echo ""

    canary watch "$PROJECT_DIR" --check-only --idle 5 &
    WATCH_PID=$!
    sleep 2
    pause

    print_section "Step 3: Prompt with Screening" "Safe AI interaction"

    echo -e "  ${BOLD}Safe prompt example:${RESET}"
    cmd "canary prompt --check-only 'Refactor process_data to use type hints'"
    canary prompt --check-only "Refactor process_data to use type hints"
    pause

    echo -e "  ${BOLD}Risky prompt example:${RESET}"
    cmd "canary prompt --check-only 'Use my AWS key AKIAIOSFODNN7EXAMPLE to deploy'"
    canary prompt --check-only "Use my AWS key AKIAIOSFODNN7EXAMPLE to deploy" || true
    pause

    # Simulate a change
    cat > "$PROJECT_DIR/app.py" << 'EOF'
from typing import Any

def process_data(data: Any) -> Any:
    """Process data with type hints."""
    processed = str(data).strip().lower()
    return processed

if __name__ == "__main__":
    result = process_data("  TEST DATA  ")
    print(result)
EOF

    print_section "Step 4: View Session Log" "Review what happened"

    cmd "canary log"
    canary log
    pause

    print_section "Step 5: Rollback if Needed" "Restore to known good state"

    cmd "canary rollback before-refactor"
    canary rollback before-refactor
    pause

    print_section "Workflow Complete" "Summary of canary protection"

    echo -e "  ${GREEN}✓${RESET} Checkpoints saved and restored"
    echo -e "  ${GREEN}✓${RESET} Watch mode detected changes"
    echo -e "  ${GREEN}✓${RESET} Prompt screening blocked risky content"
    echo -e "  ${GREEN}✓${RESET} Session log records all events"
    echo ""

    # Cleanup
    kill $WATCH_PID 2>/dev/null || true
    wait $WATCH_PID 2>/dev/null || true

    pause
}

# ============================================
# Cleanup
# ============================================
cleanup() {
    echo ""
    echo -e "${DIM}Cleaning up demo files...${RESET}"
    if [[ -d "$DEMO_DIR" ]]; then
        rm -rf "$DEMO_DIR"
    fi
    echo -e "${GREEN}Done!${RESET}"
}

# ============================================
# Main
# ============================================
main() {
    local section="${1:-quick}"

    # Check canary is installed
    if ! command -v canary &> /dev/null; then
        echo "Error: canary not found. Install with: pip install canary-tool"
        exit 1
    fi

    # Setup cleanup on exit
    trap cleanup EXIT

    case "$section" in
        quick)
            demo_quick
            ;;
        setup)
            demo_setup
            ;;
        screening)
            demo_screening
            ;;
        checkpoint)
            demo_checkpoint
            ;;
        watch)
            demo_watch
            ;;
        audit)
            demo_audit
            ;;
        guard)
            demo_guard
            ;;
        shell)
            demo_shell
            ;;
        full)
            demo_full
            ;;
        all)
            demo_quick
            demo_screening
            demo_checkpoint
            demo_watch
            demo_audit
            demo_guard
            demo_shell
            ;;
        *)
            echo "Usage: $0 [section]"
            echo ""
            echo "Sections:"
            echo "  quick      - Quick intro and help"
            echo "  setup      - Setup and configuration"
            echo "  screening  - Prompt screening/firewall"
            echo "  checkpoint - Checkpoint and rollback"
            echo "  watch      - Filesystem watch mode"
            echo "  audit      - Audit and session log"
            echo "  guard      - Guard shims"
            echo "  shell      - Interactive shell"
            echo "  full       - Complete workflow demo"
            echo "  all        - Run all demos"
            echo ""
            echo "Default: quick"
            exit 1
            ;;
    esac

    print_header "Demo Complete!"

    echo -e "  Thanks for trying canary!"
    echo ""
    echo -e "  ${BOLD}Next steps:${RESET}"
    echo -e "    • Run ${GREEN}canary${RESET} for the interactive shell"
    echo -e "    • Run ${GREEN}canary setup${RESET} to configure"
    echo -e "    • Run ${GREEN}canary docs${RESET} for more info"
    echo ""
}

main "$@"
