# Jenkins Job Configuration Tool — User Guide

<p align="center">
  <img src="multimedia/hydra_d.png" width="80" alt="Tool Logo"/>
  &nbsp;&nbsp;&nbsp;&nbsp;
  <img src="multimedia/elogo.png" width="60" alt="Ericsson"/>
</p>

---

<p align="center">
<strong>Jenkins Job Configuration Tool</strong><br/>
<em>ver. 1.7.1</em><br/><br/>
Create, maintain, and version-control Jenkins Job configurations<br/>
using a local Git/Gerrit repository.<br/><br/>
Ericsson Internal Tool — 2026
</p>

---

## Table of Contents

1. [Introduction](#introduction)
2. [Why This Tool Exists](#why-this-tool-exists)
3. [Architecture](#architecture)
4. [Installation](#installation)
5. [Quick Start](#quick-start)
6. [Complete Workflow from Scratch](#complete-workflow-from-scratch)
7. [User Interface](#user-interface)
8. [Workflows](#workflows)
9. [Sections and Parameters Reference](#sections-and-parameters-reference)
10. [Template System](#template-system)
11. [Settings](#settings)
12. [Repository File Structure](#repository-file-structure)
13. [Troubleshooting and FAQ](#troubleshooting-and-faq)
14. [Known Limitations](#known-limitations)
15. [Version History](#version-history)

---

## Introduction

The **Jenkins Job Configuration Tool** is a Python/Tkinter GUI application that bridges Jenkins job configurations and version-controlled Git/Gerrit repositories.

It decomposes monolithic `config.xml` files into individual, human-readable files (Groovy scripts, HTML, shell scripts) stored in a repository, and can reconstruct and upload them back to Jenkins.

### Main Window

![Main Window](docs/screenshots/01_main_window.png)

*The main application window with all sections populated after loading settings.*

---

## Why This Tool Exists

### The Problem

Jenkins stores job configurations as monolithic XML files. This causes:

- **No version history** — no tracking of who changed what, when, or why
- **No code review** — changes bypass review processes
- **No backup** — lost on server crash or accidental deletion
- **No collaboration** — impossible to work on different sections simultaneously
- **Difficult maintenance** — thousands of lines of mixed Groovy, HTML, and shell in one file

### The Solution

This tool:

1. **Decomposes** `config.xml` into individual, editable files
2. **Stores** them in a **Gerrit** repository (Git history, code reviews, branching)
3. **Reconstructs** the full configuration using a template system separating *content* from *infrastructure*

### Workflow

```
                    ┌─────────────────────────────────────┐
                    │        DEVELOPMENT CYCLE            │
                    └─────────────────────────────────────┘

   ┌────────────┐       ┌──────────────┐       ┌────────────┐
   │  Read Job  │──────►│ Save to Repo │──────►│ git commit │
   │  (initial) │       │              │       │ git push   │
   └────────────┘       └──────────────┘       └─────┬──────┘
                                                      │
                                                      ▼
   ┌────────────┐       ┌──────────────┐       ┌────────────┐
   │  Upload to │◄──────│  Read Repo   │◄──────│   Edit +   │
   │  Jenkins   │       │              │       │   Review   │
   └────────────┘       └──────────────┘       └────────────┘
```

---

## Architecture

```
┌──────────┐         ┌────────────────┐         ┌──────────────┐
│  JENKINS │◄──────► │   APP MEMORY   │◄──────► │   GIT REPO   │
│  server  │ REST API│  (parsed data) │ Files   │ (individual  │
│          │         │                │         │   files)     │
└──────────┘         └───────┬────────┘         └──────────────┘
                             │
                     ┌───────┴────────┐
                     │   TEMPLATE     │
                     │ job_template.xml│
                     │ (app directory)│
                     └────────────────┘
```

**Data flows:**
- **Read Job** (Jenkins → App): downloads XML, parses into sections, generates template
- **Save to Repo** (App → Git): writes sections as individual files
- **Read Repo** (Git → App): reads files, reconstructs in-memory config
- **Upload** (App → Jenkins): merges sections into template (or re-uploads raw XML)

The **Template** lives in the tool's own directory (not in the repo). It contains everything the tool does NOT decompose: SCM config, security, plugins, build wrappers, email settings structure, etc.

---

## Installation

### Getting the Tool

Clone the repository containing the tool:
```bash
git clone <gerrit-url>/SecurityRA_Utilities.git
cd SecurityRA_Utilities/JenkinsJobConfiguration
```

### Requirements

- Python 3.12+
- `requests` — HTTP client
- `Pillow` — Logo images (optional, for header logos)

```bash
pip install requests Pillow
```

> **Note**: `tkinter` is included with Python on most Linux distributions. If missing: `sudo apt install python3-tk` (Debian/Ubuntu).

### Launch

```bash
python3 jenkins_job_manager_gui.py
```

Or from the parent directory:
```bash
python3 launcher.py
```

---

## Quick Start

For experienced users — the minimal steps:

```
📥 Read Job  →  💾 Save to Repo  →  git commit  →  git push
                                                         ↕
📂 Read Repo  →  🚀 Upload to Jenkins  ←  (after edits/review)
```

If this is your first time, see the next section for a complete step-by-step guide.

---

## Complete Workflow from Scratch

This section walks you through the entire process from zero — from first launch to uploading a modified job back to Jenkins (or creating a new one with a different name).

### Prerequisites

- Python 3.12+ installed with `requests` and optionally `Pillow`
- Access to a Jenkins FEM server (URL, username, API token)
- A local Git/Gerrit repository clone (or any local directory)
- VPN/WARP connection active (if Jenkins is on the corporate network)

### Step 1: Launch the Tool

```bash
cd /path/to/SecurityRA_Utilities/JenkinsJobConfiguration
python3 jenkins_job_manager_gui.py
```

On first launch you will see:
- Empty fields in all sections
- The log shows `[INIT] ⚠ No template file` and `[INIT] ⚠ Repo root not configured`
- Status indicators: `📥 Job: ○` and `📂 Repo: ○` (not yet performed)

### Step 2: Configure Jenkins Connection

Fill in the **🔐 Jenkins Connection** section:

| Field | What to enter |
|-------|---------------|
| **URL** | Full Jenkins server URL (e.g., `https://fem10s11-eiffel004.eiffel.gic.ericsson.se:8443/jenkins`) |
| **User** | Your signum (e.g., `emaripp`) |
| **Token** | Jenkins API token (see below how to generate) |

> **SSL/TLS Note**: The tool uses `verify=False` for HTTPS connections. This means self-signed certificates on corporate Jenkins FEMs are accepted automatically — **no fingerprint configuration is needed**. You may see a urllib3 SSL warning in the terminal; these are suppressed in the GUI log.

#### Generating an API Token

1. Log in to Jenkins in your browser
2. Click your username (top-right) → **Configure**
3. Scroll to **API Token** section
4. Click **Add new Token**
5. Enter a name (e.g., "Job Config Tool")
6. Click **Generate**
7. **Copy the token immediately** — it is shown only once
8. Paste it into the tool's Token field

### Step 3: Test the Connection

Click the **🔌 Test** button next to the Token field.

- **Green dot (●)** → connection successful, authentication OK
- **Red dot (●)** → connection failed (check URL, VPN, credentials)

If the test fails, the "📥 Read from Job" and "🚀 Write to Job" buttons are automatically disabled until a successful test.

> **💡 Tip**: Hover over the status dot to see the detailed result message.

### Step 4: Set the Local Repository Path

In the **🎯 Target** section:

1. Click the **📁** button next to "Local Repo"
2. Navigate to your Git/Gerrit clone root (e.g., `/home/esignum/workspace/Git_Local/SecurityRA_Utilities`)
3. Select that directory

The tool will store job files under:
```
<selected_path>/JenkinsJobConfiguration/<job_name>/
```

### Step 5: Read an Existing Job (Template Extraction)

This is the critical first step — it downloads the job's XML, parses all sections, and **generates the template** needed for future uploads.

1. In the "Jenkins Job" field, enter the **exact job name** as it appears on Jenkins (e.g., `HYDRA-TS_TB_DST-vLITP_01`)
2. Click **📥 Read from Job**

**What happens:**
- The tool connects to Jenkins REST API
- Downloads the full `config.xml`
- Parses: Description, Parameters, Inject Variables, Build Steps, Build Name, Email Template
- Auto-populates Agent and JDK fields
- Generates `job_template.xml` in the app directory (with HYDRA:META provenance header)
- Status indicator changes: `📥 Job: ●` (green)

**Expected log output:**
```
[INFO] ▶ READ JOB — START — 'HYDRA-TS_TB_DST-vLITP_01'
[INFO] ✓ Downloaded config.xml (15234 bytes)
[INFO] ✓ Parsing complete — 8 params, 3 steps
[INFO] ─── Config Summary ───
[INFO]   • Description
[INFO]   • Inject Variables
[INFO]   • Build Name Setter
[INFO]   • Param [ActiveChoiceCascadeParam] ENVIRONMENT
[INFO]   • Param [ActiveChoiceParam] SERVER_TYPE
[INFO]   • Launcher [1] Deploy_Script
[INFO]   • Launcher [2] Verify_Script
[INFO] ──────────────────────
[INFO] ✓ Template generated: job_template.xml
[INFO] ■ READ JOB — COMPLETED
```

### Step 6: Save to the Local Repository

Now persist the parsed sections as individual editable files:

1. Click **💾 Write to Repo**
2. If the directory already exists, a confirmation dialog appears

**What gets created:**
```
<repo>/JenkinsJobConfiguration/HYDRA-TS_TB_DST-vLITP_01/
├── HYDRA-TS_TB_DST-vLITP_01-Description.html
├── HYDRA-TS_TB_DST-vLITP_01-InjectVariables.groovy
├── BuildNameSetter_Template.txt
├── email_template.html
├── Parameters/
│   ├── 00-ENVIRONMENT-Description.html
│   ├── 00-ENVIRONMENT-Script.groovy
│   ├── 00-ENVIRONMENT-FallbackScript.groovy
│   ├── 01-SERVER_TYPE-Description.html
│   ├── 01-SERVER_TYPE-Script.groovy
│   └── ...
└── ScriptLauncher/
    ├── 00.Deploy_Script_Launcher.sh
    ├── 01.Verify_Script_Launcher.sh
    └── ...
```

### Step 7: Version Control (Git/Gerrit)

```bash
cd /path/to/your/repo
git add JenkinsJobConfiguration/HYDRA-TS_TB_DST-vLITP_01/
git commit -m "No Jira - Initial extraction of HYDRA-TS_TB_DST-vLITP_01"
git push origin HEAD:refs/for/master   # for Gerrit
# or: git push                          # for plain Git
```

### Step 8: Edit the Files

Now edit any file with your preferred editor or IDE:

- **Groovy scripts** (`.groovy`) — parameter logic, variable injection
- **Shell scripts** (`.sh`) — build steps
- **HTML files** (`.html`) — descriptions, email templates
- **Template text** (`.txt`) — build name pattern

Commit and push your changes to Gerrit for code review.

### Step 9: Upload Back to Jenkins (Same Job Name)

After editing and pushing your changes:

1. Open the tool
2. Verify "Jenkins Job" field shows the correct name (e.g., `HYDRA-TS_TB_DST-vLITP_01`)
3. Click **📂 Read from Repo** — loads the modified files into memory
4. Click **🚀 Write to Job**
5. A confirmation dialog shows: "Upload to job 'HYDRA-TS_TB_DST-vLITP_01' using template + repo sections?"
6. Click **Yes**

The tool:
- Detects the job already exists on Jenkins → performs an **update**
- Merges your repo content into the template
- POSTs the full reconstructed XML to Jenkins
- Updates the HYDRA:META `merged_at` timestamp

> **⚠️ Important**: The template (`job_template.xml`) must be present. If you see `📥 Job: ○` or `📥 Job: ●` (red), run "Read from Job" first to regenerate it.

### Step 10: Upload with a Different Job Name (Clone/Create New)

To create a **new Jenkins job** based on repo files:

1. Edit the files as needed for the new job
2. In the tool, change the **"Jenkins Job"** field to the desired new name (e.g., `HYDRA-TS_TB_DST-vLITP_02`)
3. Optionally set "Repo Job" to the directory name in the repo where your files are (if different from the Jenkins job name)
4. Click **📂 Read from Repo**
5. Click **🚀 Write to Job**
6. The tool detects the job does NOT exist → performs a **create** (POST to `/createItem`)

**Example — cloning a job with modifications:**
```
1. Jenkins Job: HYDRA-TS_TB_DST-vLITP_01   → Read from Job (gets template)
2. Save to Repo                             → files saved as HYDRA-TS_TB_DST-vLITP_01/
3. Edit files in the repo
4. Jenkins Job: HYDRA-TS_TB_DST-vLITP_02   → change the target name
   Repo Job:   HYDRA-TS_TB_DST-vLITP_01   → keep reading from original directory
5. Read from Repo                           → loads files from HYDRA-TS_TB_DST-vLITP_01/
6. Write to Job                             → creates NEW job 'HYDRA-TS_TB_DST-vLITP_02'
```

> **💡 The "Repo Job" field** allows you to decouple the repo directory name from the Jenkins job name. If left empty, it defaults to the "Jenkins Job" field value.

### Complete Flow Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                    COMPLETE WORKFLOW                              │
└──────────────────────────────────────────────────────────────────┘

  ┌─────────────────┐
  │  1. FIRST RUN   │
  │  Launch tool    │
  │  Configure:     │
  │  - URL/User/Tok │
  │  - Local Repo   │
  │  - Test conn.   │
  └────────┬────────┘
           │
           ▼
  ┌─────────────────┐        ┌──────────────────┐
  │  2. READ JOB    │───────►│  3. SAVE TO REPO │
  │  (template gen) │        │  (creates files) │
  └─────────────────┘        └────────┬─────────┘
                                      │
                                      ▼
                             ┌──────────────────┐
                             │  4. GIT COMMIT   │
                             │     + PUSH       │
                             └────────┬─────────┘
                                      │
                                      ▼
                             ┌──────────────────┐
                             │  5. EDIT FILES   │
                             │  (IDE/editor)    │
                             │  git commit+push │
                             └────────┬─────────┘
                                      │
                                      ▼
  ┌─────────────────┐        ┌──────────────────┐
  │  7. WRITE JOB   │◄───────│  6. READ REPO    │
  │  (upload)       │        │  (load files)    │
  └─────────────────┘        └──────────────────┘
           │
           ├── Same name    → UPDATE existing job
           └── New name     → CREATE new job
```

### Important Notes

- **Template is mandatory for upload from repo**: without it, the tool cannot reconstruct the full XML. Always run "Read from Job" at least once per job structure.
- **Template mismatch warning**: if the template was generated from a different job than the one currently selected, the status dot turns **yellow (🟡)**. This means you should regenerate it.
- **Script approval**: if any parameter has `sandbox=false`, the tool shows a warning before upload. After uploading, you must manually approve the scripts in Jenkins (Manage Jenkins → In-process Script Approval).
- **Settings auto-save**: all fields (URL, user, token, paths, job name) are saved to `settings.json` on exit and restored on next launch.

---

## User Interface

### Connection (🔐)

![Connection Section](docs/screenshots/03_connection.png)

| Field | Description |
|-------|-------------|
| URL | Jenkins server URL |
| User | Username (signum) |
| Token | API token (masked). Generate: Jenkins → your name → Configure → API Token → Add new Token |
| 🔌 Test | Tests connectivity and authentication. Updates the status dot. |
| ● (dot) | Connection status: gray=not tested, green=OK, red=failed |
| Agent | Label Expression — auto-populated from "Restrict where this project can be run" |
| JDK | JDK name — auto-populated from job config |

### Target (🎯)

![Target Section](docs/screenshots/04_target.png)

| Field | Description |
|-------|-------------|
| Jenkins Job | Job name on Jenkins server (used for read/upload) |
| Repo Job | Directory name in the repo (defaults to Jenkins Job if empty). Allows decoupling repo structure from Jenkins job names. |
| Local Repo | Absolute path to Git/Gerrit repo root. 📁 button to browse. Files stored under `<repo>/JenkinsJobConfiguration/<repo_job>/` |

### Sections (☑)

![Sections](docs/screenshots/05_sections.png)

| Checkbox | What it controls |
|----------|------------------|
| 📝 Description | Job HTML description |
| 💉 Inject Variables | EnvInject Groovy script |
| 🏷️ Build Name | Build Name Setter template |
| 📧 Email Template | Extended Email Publisher content |
| ⚙️ Parameters | Active Choices, Boolean, String, Text, Choice parameters (⋯ for individual selection) |
| 🚀 Build Steps | Shell script launchers (⋯ for individual selection) |

**⋯ button**: Opens popup for per-item selection. Yellow checkbox text = partial selection active.

**All / None buttons**: Quickly select or deselect all section checkboxes at once.

### Action Buttons

![Action Buttons and Status Bar](docs/screenshots/06_buttons.png)

| Button | Action |
|--------|--------|
| 📥 Read from Job | Download + parse from Jenkins (generates template) |
| 📂 Read from Repo | Load from local files |
| 💾 Write to Repo | Write sections to repo |
| 🚀 Write to Job | Create/update job on Jenkins |
| 📜 History | Version changelog |
| 💾 Log | Save session log to file |
| 🔄 Reset | Clear config (credentials preserved) |
| ⊞ | Reset all windows to default size |
| Quit | Save settings and exit |
| 🐛 Save Raw XML | *(above log area)* Save the full unmodified config.xml for debugging/backup |

### Session Log

![Log Area](docs/screenshots/07_log_area.png)

*The log area shows a detailed session journal with clear START/COMPLETED/FAILED banners for each operation. Use the "💾 Log" button to save the full session log to a file.*

### Status Indicators

| Indicator | Meaning |
|-----------|----------|
| 📥 Job: ○ | Not yet performed — run "Read from Job" |
| 📥 Job: ● (green) | Template read from Jenkins successfully |
| 📥 Job: ● (yellow) | Template exists but belongs to a different job (mismatch) |
| 📥 Job: ● (red) | Read from Job failed |
| 📂 Repo: ○ | Not yet performed — run "Read from Repo" |
| 📂 Repo: ● (green) | Config loaded from repo successfully |
| 📂 Repo: ● (red) | Read from Repo failed |

> **💡 Tip**: Hover over the status dots for detailed provenance information (HYDRA:META: source URL, job name, extraction date, job version). Hover over the label for the color legend.

---

## Workflows

### Typical Use Cases

| Scenario | Steps |
|----------|-------|
| **New job to version-control** | Read from Job → Write to Repo → commit to Gerrit |
| **Update job from repo edits** | Read from Repo → Write to Job |
| **Re-sync after manual Jenkins edit** | Read from Job → Write to Repo (overwrites local) |
| **Create job on a new Jenkins** | Read from Repo → Write to Job (creates new) |
| **Clone job with a different name** | Read from Job → Write to Repo → Edit → change "Jenkins Job" name → Read from Repo → Write to Job |
| **Quick fix without touching repo** | Read from Job → Write to Job (re-uploads as-is) |

### Read from Jenkins (📥 Read from Job)

**When to use**: First-time setup, or to re-sync from the Jenkins server (e.g., someone edited the job directly).

What happens:
1. Pre-checks connectivity (blocks with error dialog if unreachable)
2. Connects via REST API (Basic Auth, HTTPS with certificate verification disabled)
3. Downloads `config.xml`
4. Normalizes XML (1.1→1.0)
5. Parses all sections
6. Extracts Agent label and JDK → populates UI fields
7. Generates template with placeholders and HYDRA:META provenance header
8. Stores raw XML in memory for direct re-upload
9. Logs a Config Summary listing all found items

> **Note**: After Read from Job, you have two options:
> - **Write to Repo** — to persist the parsed sections to files
> - **Write to Job** — to immediately push the (unmodified) config back (useful for cloning to another server)

### Save to Repository (💾 Write to Repo)

**When to use**: After Read from Job, or after making in-memory modifications via the item selector.

What happens:
1. Checks Local Repo path is valid
2. Creates directory structure: `<repo>/JenkinsJobConfiguration/<repo_job>/`
3. If directory already exists, asks for overwrite confirmation
4. Writes each enabled section as an individual file
5. Parameter files include metadata comment headers (type, choice type, referenced parameters, sandbox, default value)
6. Build step files are named from "Script Name:" comments
7. Parameters are ordered by their numeric prefix (00, 01, 02...)

> **⚠️ Overwrite warning**: Write to Repo overwrites existing files for the selected sections. Files for deselected sections are left untouched. Files that no longer exist in the config (e.g., a deleted parameter) will NOT be removed — delete them manually from the repo if needed.

### Read from Repository (📂 Read from Repo)

**When to use**: When you (or a colleague) have edited the files in the repo and want to upload the changes to Jenkins.

What happens:
1. Reads files from the repo directory structure
2. Logs exact paths searched (job dir, params dir, launchers dir)
3. Parses parameter metadata from comment headers
4. Reconstructs the full in-memory configuration
5. Logs a Config Summary
6. You can then Write to Job

> **Note**: Read from Repo does NOT generate a template. The template must already exist (from a previous Read from Job). If the template is missing or mismatched (🔴 or 🟡 indicator), you must Read from Job first.

### Upload to Jenkins (🚀 Write to Job)

**When to use**: To apply changes to the Jenkins server.

What happens:
1. **If raw XML is available** (from Read from Job in the same session) AND source is "job": uploads the original XML directly — this is the safest option (raw passthrough)
2. **If source is "repo"** (from Read from Repo): merges content sections into template placeholders to reconstruct the full `config.xml` using Smart Upload:
   - Selected items from repo are injected into template
   - Deselected items preserve original Jenkins content (if raw_xml available)
   - Deleted items (in repo but not in template) are removed from the XML
   - Parameters are ordered by their numeric prefix (00, 01, 02...)
3. Validates the generated XML before uploading (saves debug file on failure)
4. Refreshes CSRF crumb immediately before POST
5. Detects whether job exists:
   - **Exists** → updates (POST to `/job/{name}/config.xml`)
   - **Does not exist** → creates (POST to `/createItem`)
6. Shows confirmation dialog before proceeding — click **Yes** to upload or **No** to cancel
7. If scripts have sandbox disabled, shows a Script Approval warning with the list of affected items
8. Updates HYDRA:META `merged_at` timestamp in the generated XML

> **💡 Tip**: If you Read from Job and then immediately Write to Job without changes, it's a safe no-op that verifies your connection works.

### Editing Files in the Repository

After saving to repo, you can edit files with any text editor or IDE:

- **Groovy scripts** (`.groovy`) — edit parameter logic, inject variables
- **Shell scripts** (`.sh`) — modify build steps
- **HTML files** (`.html`) — update descriptions, email templates
- **Template text** (`.txt`) — change build name pattern

**Workflow after editing**:
```
1. Edit files in your IDE
2. git add / git commit / git push to Gerrit
3. (Optional) Gerrit code review & merge
4. Open tool → Read from Repo → Write to Job
```

### Working with Multiple Jobs

The tool works with one job at a time. To manage multiple jobs:

1. Change the "Jenkins Job" field to a different job name
2. Read from Job / Read from Repo for that job
3. Each job gets its own subdirectory in the repo

All jobs share the same Local Repo root but have separate directories:
```
<repo>/JenkinsJobConfiguration/
├── Job_A/
├── Job_B/
└── Job_C/
```

> **⚠️ Note**: The template (`job_template.xml`) is per-tool-instance, not per-job. If you switch between jobs with very different structures, re-run Read from Job to regenerate the template for the current job before uploading. The status dot turns **yellow** when a mismatch is detected.
>
> **💡 Workaround**: You can manually rename templates (e.g., `job_template_JobA.xml`, `job_template_JobB.xml`) and rename back to `job_template.xml` before uploading a specific job.

### Partial Item Selection (⋯)

For Parameters and Build Steps, you can select which individual items to include:

1. Load a config (Read from Job or Read from Repo)
2. Click the **⋯** button next to "Parameters" or "Build Steps"
3. A popup appears listing all items with checkboxes
4. Uncheck items you want to exclude
5. Click **✓ Apply**

**Visual feedback**:
- All items selected → normal white checkbox text
- Some items selected → **yellow** checkbox text (partial)
- No items selected → checkbox unchecked

This filtering applies to both **Write to Repo** and **Write to Job**.

### Reset (🔄)

Reset clears:
- ✗ Loaded configuration (in-memory)
- ✗ Raw XML
- ✗ Item selections

Reset preserves:
- ✓ Jenkins URL, User, Token
- ✓ Agent, JDK
- ✓ Job Name, Repo Job, Local Repo path
- ✓ Section checkbox states

---

## Sections and Parameters Reference

### Description

- **XML source**: `<description>` (root-level element)
- **File**: `<JobName>-Description.html`
- **Format**: HTML — can contain rich text, links, embedded build badges
- **Notes**: This is the text shown at the top of the Jenkins job page

### Parameters

Each parameter produces **up to 3 files**:

| File | Content |
|------|---------|
| `NN-PARAM_NAME-Description.html` | HTML description + metadata header |
| `NN-PARAM_NAME-Script.groovy` | Main Groovy script (logic) |
| `NN-PARAM_NAME-FallbackScript.groovy` | Fallback script (returned on error) |

The **NN prefix** (00, 01, 02...) preserves the parameter order as defined in Jenkins. On upload, parameters are reordered according to these numeric prefixes regardless of their original position in the template.

**Supported parameter types:**

| Tag | Type |
|-----|------|
| `org.biouno.unochoice.ChoiceParameter` | Active Choices |
| `org.biouno.unochoice.CascadeChoiceParameter` | Active Choices Reactive |
| `org.biouno.unochoice.DynamicReferenceParameter` | Active Choices Reactive Reference |
| `*BooleanParameterDefinition` | Boolean |
| `*StringParameterDefinition` | String |
| `*TextParameterDefinition` | Text (multiline) |
| `*ChoiceParameterDefinition` | Choice (static dropdown) |

**Extracted fields per parameter:**
- `name` — Parameter name
- `type` — Detected type
- `description` — HTML description
- `script` — Main Groovy script
- `fallback_script` — Fallback script
- `choiceType` — UI rendering (PT_SINGLE_SELECT, PT_MULTI_SELECT, PT_CHECKBOX, etc.)
- `referencedParameters` — Dependencies (comma-separated)
- `sandbox` — Script sandbox mode (true/false)
- `filterable` — Whether the parameter is filterable
- `visibleItemCount` — Number of visible items
- `defaultValue` — Default value (supports multiline for TextParameter)

**Script search paths** (multiple XML formats):
- `.//script/secureScript/script`
- `.//groovyScript/secureScript/script`
- `.//script/script`, `.//groovyScript/script`

**Parameter Description header example:**
```html
<!--
Parameter Configuration:
- Parameter Type: Active Choices Reactive Parameter
- Choice Type: Single Select
- Referenced parameters: ENVIRONMENT, REGION
- Sandbox: true
- Filterable: false
- Visible Item Count: 1
- Default Value: (none)
-->
```

### Inject Variables

- **XML paths** (searched in order):
  1. `EnvInjectBuildWrapper/info/secureGroovyScript/script`
  2. `EnvInjectBuildWrapper/info/groovyScriptContent`
  3. `EnvInjectJobProperty/info/secureGroovyScript/script`
  4. `EnvInjectJobProperty/info/groovyScriptContent`
- **File**: `<JobName>-InjectVariables.groovy`
- **Note**: EnvInject has old (`groovyScriptContent`) and new (`secureGroovyScript`) formats. Always runs unsandboxed.

### Build Steps

- **XML**: `hudson.tasks.Shell/command`
- **Files**: `ScriptLauncher/NN.ScriptName_Launcher.sh`
- **Naming**: The tool looks for a `# Script Name: XXX` comment in the shell content to generate a meaningful filename. If not found, defaults to `NN.StepN_Launcher.sh`
- **Ordering**: The NN prefix (00, 01, 02...) preserves execution order. Files are read back sorted by name.

### Build Name Setter

- **XML paths**: `BuildNameUpdater/buildName`, `BuildNameSetter/template`
- **File**: `BuildNameSetter_Template.txt`

### Email Template

- **XML**: `ExtendedEmailPublisher/defaultContent`
- **File**: `email_template.html`

### Agent Label

- **XML**: `<assignedNode>` (only when `<canRoam>false</canRoam>`)
- **Meaning**: "Restrict where this project can be run" checkbox + Label Expression
- **If canRoam=true**: no restriction, field empty

### JDK

- **XML**: `<jdk>` (ignored if "(System)" or absent)

---

## Template System

### What is the Template?

The template (`job_template.xml`) is a copy of the job's full `config.xml` where all editable content has been replaced by placeholder markers. Think of it as a "skeleton" — it holds the infrastructure and structure, while the "flesh" (content) lives in the repo files.

### Template Provenance (HYDRA:META)

Every generated template includes a metadata comment block at the top:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!--
HYDRA:META
  extracted_from : https://jenkins.example.com
  job_name       : MyPipeline
  extracted_at   : 2026-06-30 10:27:14 UTC
  job_version    : 42
-->
```

- **extracted_from** — Jenkins URL the template was read from
- **job_name** — name of the Jenkins job
- **extracted_at** — UTC timestamp of extraction
- **job_version** — version number from the Jenkins job XML, if present

When **Write to Job** or any config generation runs (merge), the block is updated with an additional `merged_at` field, while preserving all original extraction info.

The status indicator tooltip displays these provenance details when you hover over the dot.

### When is it Generated?

- **Automatically** during **Read from Job** — every time you download from Jenkins
- **Never** during Read from Repo — the template must already exist

### When Should I Regenerate It?

Regenerate the template (by running Read from Job again) when:
- You change plugin settings on Jenkins (e.g., add an email recipient, change SCM branch)
- You add/remove parameters directly on Jenkins
- You change build wrappers, post-build actions, or security settings
- The status dot is yellow (template belongs to a different job)
- The upload produces unexpected results

### Placeholders

| Marker | Section |
|--------|---------|
| `<!-- HYDRA:DESCRIPTION -->` | Description |
| `<!-- HYDRA:PARAM_SCRIPT -->` | Parameter script (per param) |
| `<!-- HYDRA:PARAM_FALLBACK -->` | Parameter fallback (per param) |
| `<!-- HYDRA:INJECT_GROOVY -->` | Inject variables |
| `<!-- HYDRA:BUILD_STEP -->` | Build step (per step) |
| `<!-- HYDRA:EMAIL_TEMPLATE -->` | Email template |
| `<!-- HYDRA:BUILD_NAME -->` | Build name |

### What the Template Preserves

- SCM configuration
- Security settings
- Build environment
- Plugin configurations
- Email recipients/triggers
- Node assignment
- Post-build actions

### ADD Mode (v1.7.1)

When the template has no `<parameterDefinitions>` section at all (e.g., a job that originally had no parameters), but repo files contain parameters, the generator creates the full `<parameterDefinitions>` section and injects all repo parameters into `<properties>`, instead of silently skipping them.

---

## Settings

Auto-saved to `settings.json` on exit, loaded on startup.

### Settings Fields

| Field | Description | Example |
|-------|-------------|---------|
| `url` | Jenkins server base URL | `https://fem10s11-eiffel004.eiffel.gic.ericsson.se:8443/jenkins` |
| `user` | Jenkins username | `emaripp` |
| `token` | API token (stored in plain text — keep file secure) | `11a2b3c4d5e6f7...` |
| `agent` | Default agent label | `Hydra_enm_openstack` |
| `jdk` | Default JDK installation name | `JDK 11` |
| `job_name` | Last used job name | `HYDRA-TS_TB_DST-vLITP_01` |
| `repo_job_name` | Repo directory name (if different from job_name) | `HYDRA_DST_01` |
| `repo_root` | Absolute path to local Git repository root | `/home/user/workspace/Git_Local/SecurityRA_Utilities` |
| `repo_output_dir` | Subdirectory name within repo for job configs | `JenkinsJobConfiguration` |
| `parameters_dir` | Subdirectory for parameter files | `Parameters` |
| `launchers_dir` | Subdirectory for build step scripts | `ScriptLauncher` |
| `template_filename` | Name of the generated template file | `job_template.xml` |
| `sections` | Which sections are enabled (true/false per section) | `{"description": true, ...}` |
| `window_geometry` | Main window size/position | `980x720+100+100` |

### Example `settings.json`

```json
{
  "url": "https://jenkins.example.com",
  "user": "esignum",
  "token": "xxxxx",
  "agent": "ENM_AGENT",
  "jdk": "JDK 11",
  "job_name": "MyJob",
  "repo_job_name": "",
  "repo_root": "/home/user/workspace/MyRepo",
  "repo_output_dir": "JenkinsJobConfiguration",
  "parameters_dir": "Parameters",
  "launchers_dir": "ScriptLauncher",
  "template_filename": "job_template.xml",
  "sections": { "description": true, "parameters": true, "inject": true,
                "build_steps": true, "build_name": true, "email": true }
}
```

> **⚠️ Security Note**: The API token is stored in plain text in `settings.json`. Keep this file private and do not commit it to the repository.

---

## Repository File Structure

```
<repo_root>/
└── JenkinsJobConfiguration/
    └── <repo_job_name>/
        ├── <JobName>-Description.html
        ├── <JobName>-InjectVariables.groovy
        ├── BuildNameSetter_Template.txt
        ├── email_template.html
        ├── Parameters/
        │   ├── 00-PARAM_NAME-Description.html
        │   ├── 00-PARAM_NAME-Script.groovy
        │   ├── 00-PARAM_NAME-FallbackScript.groovy
        │   └── ...
        └── ScriptLauncher/
            ├── 00.DeployScript_Launcher.sh
            └── ...
```

---

## Troubleshooting and FAQ

### Common Issues

| Problem | Solution |
|---------|----------|
| Template not found on Upload | Read from Job at least once to generate it |
| Template dot is yellow | Template belongs to a different job — re-run Read from Job |
| Connection error / 401 | Check URL, token validity, network access |
| Connection error / 403 | Token may lack permissions or CSRF issue |
| Connection test shows red dot | Verify VPN/WARP, DNS, URL correctness |
| XML 1.1 rejected on Upload | Automatic normalization handles this — should not occur |
| Repository not set | Set Local Repo path via 📁 or type absolute path |
| No items in ⋯ selector | Load a config first (Read from Job or Read from Repo) |
| Upload creates but doesn't update | Job name may have a typo — names are case-sensitive |
| Saved files are empty | The section may be empty in the Jenkins job |
| Read Repo finds no parameters | Check that files follow `NN-NAME-Suffix` naming. Note: hyphens in parameter names are supported (v1.6.2+) |
| Read Repo warns "launchers_dir not found" | Check that the folder name in settings matches the actual directory (case-sensitive: `ScriptLauncher` not `ScriptLauncer`) |
| 0 launchers warning on Upload | The repo has no shell scripts but Jenkins job has some — the tool warns before proceeding to avoid data loss |
| Script approval needed after Upload | Go to Manage Jenkins → In-process Script Approval and approve pending scripts |

### Frequently Asked Questions

**Q: Do I need to be on the VPN to use this tool?**
A: Yes, if your Jenkins server is only accessible via the corporate network.

**Q: Can I use this tool without Gerrit?**
A: Yes. Any local directory works as the "Local Repo". Gerrit is recommended for code review but not required.

**Q: What happens if I Upload and the job is broken?**
A: If you previously ran Read from Job, the raw XML is in memory. You can immediately Upload again to restore the original. For extra safety, use "🐛 Save Raw XML" before making changes to keep a backup.

**Q: Can two people use this tool on the same job simultaneously?**
A: The tool itself has no locking. Use Gerrit's review workflow to coordinate changes. The last upload wins.

**Q: My job has plugins the tool doesn't parse. Will Upload break them?**
A: No. Unparsed sections stay in the template unchanged. Only the sections listed in this guide (Description, Parameters, Inject, Build Steps, Build Name, Email) are extracted and replaced.

**Q: I added a new parameter on Jenkins. How do I get it into the repo?**
A: Run Read from Job again → Write to Repo. This regenerates both the template and the parameter files.

**Q: What if I edit files in the repo and forget to Read from Repo before Upload?**
A: If you have raw XML in memory (from a previous Read from Job in the same session), Upload will use that instead of your repo edits. To be safe: Reset → Read from Repo → Write to Job.

**Q: The Agent/JDK fields didn't get populated after Read from Job. Why?**
A: The job either has "canRoam" enabled (no agent restriction) or uses the default system JDK. These are normal — the fields only populate when explicit values are set in the job.

**Q: Can I upload to a job with a different name than the one I read?**
A: Yes! Change the "Jenkins Job" field to the desired name after loading the config. If the job doesn't exist on Jenkins, it will be created. This is the recommended way to clone jobs.

**Q: Does the tool handle SSL certificates?**
A: The tool disables SSL certificate verification (`verify=False`). This means self-signed certificates on corporate Jenkins FEMs are accepted without configuration. No fingerprint setup is required.

**Q: What is the "Repo Job" field for?**
A: It allows you to read files from a different directory name than the one you're uploading to. For example, read files from the "HYDRA_Template" directory in the repo, but upload them as "HYDRA_Production_Job" on Jenkins.

### Log Messages Reference

| Prefix | Meaning |
|--------|---------|
| `[INIT]` | Application startup |
| `[INFO] ▶` | Operation started |
| `[INFO] ✓` | Operation succeeded |
| `[INFO] ■` | Operation finished (with START/COMPLETED/FAILED banners) |
| `[WARNING]` | Non-fatal issue (missing field, empty section) |
| `[ERROR] ✗` | Operation failed |
| `[PARSE]` | XML parsing details |
| `[SAVE]` | File write operations |
| `[READ]` | File read operations |
| `[API]` | Jenkins API communication |
| `[TEMPLATE]` | Template generation |
| `[DEBUG]` | Detailed internal state (visible if logging is set to DEBUG) |

---

## Known Limitations

- **One template per tool instance** — switching between structurally different jobs requires re-running Read from Job to regenerate the template (yellow dot warns you)
- **No automatic file cleanup** — if you remove a parameter from Jenkins, the old file remains in the repo (delete it manually). However, Smart Upload will exclude deleted items from the uploaded XML.
- **No diff/preview** — there's no visual diff before Upload; the tool uploads as-is
- **Token in plain text** — `settings.json` stores the API token unencrypted
- **No folder-level jobs** — nested Jenkins folder paths (e.g., `folder/subfolder/job`) are not supported
- **Single-server** — the tool connects to one Jenkins server per session (change URL to switch)
- **TextParameter multiline default** — multiline default values are preserved in the header but the header format uses a multi-line block (v1.7.1+)

---

## Version History

| Version | Highlights |
|---------|-----------|
| 1.7.1 | TextParameterDefinition support; ADD mode for empty templates; multiline default value fix |
| 1.7.0 | Parameter reordering by numeric prefix; 🔌 Test connectivity button; connection status indicator; pre-check before Read/Upload |
| 1.6.2 | Fix parameter name parsing with hyphens |
| 1.6.1 | Status indicators redesign (split label/dot, independent tooltips, yellow mismatch dot, real-time update) |
| 1.5.0 | Template provenance (HYDRA:META header); metadata tooltip on status dot |
| 1.4.1 | Build step injection into empty `<builders>`; safety guards; launcher directory warnings |
| 1.4.0 | Config Summary; Read Repo diagnostics; ChoiceParameterDefinition; type change detection; Repo Job field; overwrite confirmation; script approval warning |
| 1.2.0 | Full parameter lifecycle; new parameter addition from repo; XML validation; window geometry persistence |
| 1.1.0 | Smart Upload (item deletion, deselected item preservation); name-based parameter matching; enhanced logging |
| 1.0.0 | Initial release |

---

*Jenkins Job Configuration Tool — ver. 1.7.1 — Ericsson 2026*
