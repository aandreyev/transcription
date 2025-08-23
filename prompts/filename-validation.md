Review this filename and fix any issues. Make it professional and logical.

Proposed: {proposed_filename}
Original: {original_filename}

CRITICAL ISSUES TO FIX:
- ❌ Duplicate dates: "20250720 20250526 TA" → "20250526 TA"
- ❌ "Processed" suffix: "re Topic - Processed" → "re Topic"
- ❌ Duplicate names: "John Smith and Smith" → "John Smith"
- ❌ Person as topic: "re John Smith" → use actual topic or remove
- ❌ Duplicate words: "re re Topic" → "re Topic"

If the filename has issues, return ONLY the corrected filename.
If the filename is fine, return ONLY the word "VALID".

Examples:
- Input: "20250720 20250526 TA Michael Murray" → Output: "20250526 TA Michael Murray"
- Input: "20250526 TA Anthony re Pickles - Processed" → Output: "20250526 TA Anthony re Pickles"
- Input: "20250526 TA Michael Murray re Data Patents - 15min" → Output: "VALID"
