from pathlib import Path
BRAIN_DIR=Path(__file__).with_name('brains')
BRAIN_FILES=('common_base.md','notes_routine.md','project_logic.md','logs_issues.md','research_live.md','coding_security.md','writing_drafts.md')
def load_brain():return '\n\n'.join((BRAIN_DIR/n).read_text(encoding='utf-8') for n in BRAIN_FILES if (BRAIN_DIR/n).is_file())
