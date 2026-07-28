# 🔧 Jenkins Job Configuration Tool

<p align="center">
  <img src="multimedia/hydra_d.png" width="80" alt="Hydra Logo"/>
  &nbsp;&nbsp;&nbsp;&nbsp;
  <img src="multimedia/elogo.png" width="60" alt="Ericsson"/>
</p>

<p align="center">
  <strong>Version 1.7.1</strong> · Python 3.12+ · Tkinter GUI<br/>
  <em>Create, maintain, and version-control Jenkins job configurations</em>
</p>

---

## What is this?

A desktop GUI tool that bridges **Jenkins job configurations** and **Git/Gerrit repositories**.

Jenkins stores jobs as monolithic XML files with no version history, no code review, and no backup. This tool solves that by:

1. **Decomposing** `config.xml` into individual, human-readable files (Groovy scripts, HTML descriptions, shell scripts)
2. **Storing** them in a Git repository (version history, code reviews, branching, collaboration)
3. **Reconstructing** the full configuration using a template system that separates *editable content* from *infrastructure XML*

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
                     └────────────────┘
```

## Key Features

| Feature | Description |
|---------|-------------|
| 📥 **Read from Job** | Download config.xml from Jenkins, parse all sections, auto-generate template |
| 💾 **Write to Repo** | Save individual files (Groovy, HTML, shell) to a local Git directory |
| 📂 **Read from Repo** | Reconstruct configuration from edited local files |
| 🚀 **Write to Job** | Upload to Jenkins — creates new or updates existing job |
| 🔌 **Connectivity Test** | Pre-check Jenkins reachability and authentication |
| ⚙️ **Smart Upload** | Only selected items are pushed; deselected items preserve original content |
| 📄 **Template System** | Separates editable content from infrastructure XML (HYDRA:META provenance) |
| 🔄 **Job Cloning** | Read from one job, change the name, upload as a new job |

### Supported Sections

- Job Description (HTML)
- Parameters: Active Choices, Reactive, Reactive Reference, Boolean, String, Text, Choice
- Inject Variables (EnvInject Groovy)
- Build Steps (Shell scripts)
- Build Name Setter
- Email Template (Extended Email Publisher)

## Requirements

- **Python 3.12+**
- **`requests`** — HTTP client for Jenkins API
- **`Pillow`** — (Optional) Logo images in the header

```bash
pip install requests Pillow
```

> `tkinter` is included with Python on most Linux distributions. If missing: `sudo apt install python3-tk`

## Quick Start

```bash
# Clone this repo
git clone git@github.com:MarcoIppo/JenkinsJobConfiguration.git
cd JenkinsJobConfiguration

# Install dependencies
pip install requests Pillow

# Launch
python3 jenkins_job_manager_gui.py
```

### Typical Workflow

```
1. Configure URL, user, API token    → 🔌 Test connection
2. Enter Jenkins job name            → 📥 Read from Job (generates template)
3. 💾 Write to Repo                  → Files saved locally
4. Edit files (Groovy, HTML, shell)  → git commit + push
5. 📂 Read from Repo                 → 🚀 Write to Job (update or create)
```

## Repository Output Structure

When you save a job to repo, the tool creates:

```
JenkinsJobConfiguration/<job_name>/
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
    ├── 00.ScriptName_Launcher.sh
    └── ...
```

## Documentation

- **[User Guide (EN)](docs/UserGuide.md)** — Complete documentation with step-by-step workflows
- **[User Guide (IT)](docs/UserGuide_IT.md)** — Guida utente in italiano

## Template System (HYDRA:META)

The tool generates a `job_template.xml` with all editable content replaced by placeholders (`<!-- HYDRA:DESCRIPTION -->`, `<!-- HYDRA:PARAM_SCRIPT -->`, etc.). A provenance header tracks origin:

```xml
<!--
HYDRA:META
  extracted_from : https://jenkins.example.com
  job_name       : MyPipeline
  extracted_at   : 2026-06-30 10:27:14 UTC
  job_version    : 42
-->
```

This ensures you always know where the template came from and when it was last merged.

## Version History

| Version | Highlights |
|---------|-----------|
| **1.7.1** | TextParameter support; ADD mode for empty templates |
| **1.7.0** | 🔌 Connectivity test; parameter reordering; pre-check before operations |
| **1.6.x** | Status indicators redesign; hyphen-in-name fix |
| **1.5.0** | Template provenance (HYDRA:META) |
| **1.4.0** | ChoiceParameter; Repo Job field; script approval warning |
| **1.2.0** | Full parameter lifecycle; XML validation |
| **1.1.0** | Smart Upload; name-based matching |
| **1.0.0** | Initial release |

See the full [changelog in the source](jenkins_job_manager_gui.py) or the [User Guide](docs/UserGuide.md#version-history).

## License

Ericsson Internal Tool — 2026

---

<p align="center">
  <em>Built for the Security RA team · Ericsson</em>
</p>
