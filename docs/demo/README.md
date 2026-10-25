# ENGANO demo videos

`make demo` serves `index.html` at http://127.0.0.1:8765/ (player, chapters, transcript; `serve.py` supports seeking).

* `engano-demo.mp4` - product walkthrough (about 3.5 minutes, narrated, captions). A real recording of the running app: a brand
  manager sets up a workspace and a rule, a creator drafts and is checked, a reviewer comments and rejects, the creator revises
  (history shows what changed), the manager watches. Includes image and website checks. The last card lists what is still missing.
* `engano-demo-dev.mp4` - example: a brand manager assigns website work to a developer; ENGANO checks the page and says what must be
  fixed; a reviewer verifies it. No status card.

The `.json` files hold chapter times and caption text. The build scripts (narration, voice, browser recording, assembly) live next to
the submission files in `submission/round2/build/`, outside this repository.
