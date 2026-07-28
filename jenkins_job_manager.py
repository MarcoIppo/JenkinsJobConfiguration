"""
Jenkins Job Configuration Manager — Backend
Handles Jenkins API communication, XML parsing, file I/O, and template management.
"""

import os
import re
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET
from typing import Optional

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger("JenkinsJobManager")

# --- Constants ---

PLACEHOLDER_DESCRIPTION = "<!-- HYDRA:DESCRIPTION -->"
PLACEHOLDER_PARAM_SCRIPT = "<!-- HYDRA:PARAM_SCRIPT -->"
PLACEHOLDER_PARAM_FALLBACK = "<!-- HYDRA:PARAM_FALLBACK -->"
PLACEHOLDER_INJECT_GROOVY = "<!-- HYDRA:INJECT_GROOVY -->"
PLACEHOLDER_BUILD_STEP = "<!-- HYDRA:BUILD_STEP -->"
PLACEHOLDER_EMAIL_TEMPLATE = "<!-- HYDRA:EMAIL_TEMPLATE -->"
PLACEHOLDER_BUILD_NAME = "<!-- HYDRA:BUILD_NAME -->"

# Regex to match the HYDRA metadata header block at the top of a template/generated file
_TEMPLATE_META_RE = re.compile(
    r'<!--\s*HYDRA:META\s*\n(.*?)-->\s*\n?',
    re.DOTALL
)


def build_template_meta(source_url: str, job_name: str, extracted_at: str,
                         job_version: str = "") -> str:
    """Return the XML comment block that records template provenance."""
    lines = [
        "HYDRA:META",
        f"  extracted_from : {source_url}",
        f"  job_name       : {job_name}",
        f"  extracted_at   : {extracted_at}",
    ]
    if job_version:
        lines.append(f"  job_version    : {job_version}")
    lines.append("")   # blank line before closing -->
    return "<!--\n" + "\n".join(lines) + "-->\n"


def build_merged_meta(original_meta: dict, merged_at: str) -> str:
    """Return the XML comment block for a generated/merged file, preserving extraction info."""
    lines = [
        "HYDRA:META",
        f"  extracted_from : {original_meta.get('extracted_from', 'unknown')}",
        f"  job_name       : {original_meta.get('job_name', 'unknown')}",
        f"  extracted_at   : {original_meta.get('extracted_at', 'unknown')}",
    ]
    if original_meta.get("job_version"):
        lines.append(f"  job_version    : {original_meta['job_version']}")
    lines.append(f"  merged_at      : {merged_at}")
    lines.append("")
    return "<!--\n" + "\n".join(lines) + "-->\n"


def parse_template_meta(xml_text: str) -> dict:
    """Extract HYDRA:META fields from an XML comment header. Returns empty dict if absent."""
    m = _TEMPLATE_META_RE.search(xml_text)
    if not m:
        return {}
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            if key and key != "HYDRA:META":
                meta[key] = value
    return meta


def format_meta_tooltip(meta: dict) -> str:
    """Format HYDRA:META dict as a human-readable tooltip string."""
    if not meta:
        return "No provenance information available."
    parts = []
    if meta.get("extracted_from"):
        parts.append(f"🌐 Source  : {meta['extracted_from']}")
    if meta.get("job_name"):
        parts.append(f"🔧 Job     : {meta['job_name']}")
    if meta.get("extracted_at"):
        parts.append(f"📅 Extracted: {meta['extracted_at']}")
    if meta.get("job_version"):
        parts.append(f"🏷  Version : {meta['job_version']}")
    if meta.get("merged_at"):
        parts.append(f"🔀 Merged  : {meta['merged_at']}")
    return "\n".join(parts)

PARAM_TYPE_MAP = {
    "org.biouno.unochoice.ChoiceParameter": "active_choices",
    "org.biouno.unochoice.CascadeChoiceParameter": "active_choices_reactive",
    "org.biouno.unochoice.DynamicReferenceParameter": "active_choices_reactive_reference",
}

DEFAULT_SETTINGS = {
    "url": "https://jenkins.example.com",
    "user": "",
    "token": "",
    "agent": "",
    "jdk": "",
    "job_name": "",
    "template_filename": "job_template.xml",
    "repo_root": "",
    "repo_output_dir": "JenkinsJobConfiguration",
    "parameters_dir": "Parameters",
    "launchers_dir": "ScriptLauncher",
    "sections": {
        "description": True,
        "parameters": True,
        "inject": True,
        "build_steps": True,
        "build_name": True,
        "email": True,
    },
}


# --- Settings ---

def load_settings(path: str) -> dict:
    """Load settings from JSON file, merging with defaults."""
    settings = dict(DEFAULT_SETTINGS)
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                saved = json.load(f)
            settings.update(saved)
            # Merge nested sections
            if "sections" in saved:
                settings["sections"] = {**DEFAULT_SETTINGS["sections"], **saved["sections"]}
        except Exception as e:
            logger.warning(f"Failed to load settings: {e}")
    return settings


def save_settings(path: str, settings: dict):
    """Save settings to JSON file."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)


# --- Jenkins Client ---

class JenkinsClient:
    """Handles communication with Jenkins REST API."""

    def __init__(self, url: str, user: str, token: str):
        self.base_url = url.rstrip("/")
        self.user = user
        self.token = token
        self.session = requests.Session()
        self.session.auth = (user, token)
        self.session.verify = False
        self.crumb_header = None
        self.crumb_value = None

    def _refresh_crumb(self):
        """Fetch CSRF crumb from Jenkins."""
        try:
            resp = self.session.get(f"{self.base_url}/crumbIssuer/api/json", timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                self.crumb_header = data["crumbRequestField"]
                self.crumb_value = data["crumb"]
                self.session.headers[self.crumb_header] = self.crumb_value
                logger.info("[API] CSRF crumb refreshed")
            else:
                logger.warning(f"[API] Crumb request returned {resp.status_code}")
        except Exception as e:
            logger.warning(f"[API] Could not fetch crumb: {e}")

    def read_config(self, job_name: str) -> str:
        """Download config.xml for a job."""
        url = f"{self.base_url}/job/{job_name}/config.xml"
        logger.info(f"[API] GET {url}")
        resp = self.session.get(url, timeout=30)
        resp.encoding = "utf-8"
        resp.raise_for_status()
        return resp.text

    def upload_config(self, job_name: str, xml_content: str, create: bool = False):
        """Upload config.xml to Jenkins (create or update)."""
        self._refresh_crumb()
        headers = {"Content-Type": "application/xml; charset=UTF-8"}
        xml_content = normalize_xml_declaration(xml_content)

        if create:
            url = f"{self.base_url}/createItem?name={job_name}"
        else:
            url = f"{self.base_url}/job/{job_name}/config.xml"

        logger.info(f"[API] POST {url} ({'create' if create else 'update'})")
        resp = self.session.post(url, data=xml_content.encode("utf-8"), headers=headers, timeout=30)
        if resp.status_code >= 400:
            body = resp.text[:500] if resp.text else "(empty response body)"
            logger.error(f"[API] Upload failed — HTTP {resp.status_code}: {body}")
            resp.raise_for_status()
        logger.info(f"[API] Upload successful ({resp.status_code})")

    def job_exists(self, job_name: str) -> bool:
        """Check if a job exists."""
        url = f"{self.base_url}/job/{job_name}/api/json"
        try:
            resp = self.session.get(url, timeout=10)
            return resp.status_code == 200
        except Exception:
            return False

    def check_connection(self) -> tuple:
        """Test connectivity and authentication to Jenkins.

        Returns:
            (success: bool, message: str) — True if reachable and authenticated.
        """
        url = f"{self.base_url}/api/json?tree=mode,nodeDescription"
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 200:
                return True, "Connection OK — authenticated successfully"
            elif resp.status_code == 401:
                return False, "Authentication failed (401) — check user/token"
            elif resp.status_code == 403:
                return False, "Access denied (403) — user lacks permissions"
            else:
                return False, f"Unexpected response: HTTP {resp.status_code}"
        except requests.exceptions.ConnectionError as e:
            err_msg = str(e)
            if "NameResolutionError" in err_msg or "Name or service not known" in err_msg:
                return False, "DNS resolution failed — hostname not reachable"
            elif "Connection refused" in err_msg:
                return False, "Connection refused — server may be down"
            else:
                return False, f"Connection error: {err_msg[:100]}"
        except requests.exceptions.Timeout:
            return False, "Connection timed out (10s) — server unreachable"
        except Exception as e:
            return False, f"Unexpected error: {str(e)[:100]}"


# --- XML Utilities ---

def normalize_xml_declaration(xml_text: str) -> str:
    """Convert XML 1.1 to 1.0 and remove standalone attribute."""
    xml_text = re.sub(
        r'<\?xml\s+version=["\']1\.1["\']',
        '<?xml version="1.0"',
        xml_text
    )
    xml_text = re.sub(r'\s+standalone=["\'][^"\']*["\']', '', xml_text)
    return xml_text


# --- XML Parser ---

class ConfigParser:
    """Parses Jenkins config.xml into structured sections."""

    def __init__(self, xml_text: str):
        self.raw_xml = xml_text
        # Normalize XML 1.1 → 1.0 for ElementTree compatibility
        normalized = normalize_xml_declaration(xml_text)
        self.tree = ET.ElementTree(ET.fromstring(normalized))
        self.root = self.tree.getroot()

    def parse_all(self) -> dict:
        """Parse all sections from config.xml."""
        config = {
            "description": self.parse_description(),
            "parameters": self.parse_parameters(),
            "inject_variables": self.parse_inject_variables(),
            "build_steps": self.parse_build_steps(),
            "build_name": self.parse_build_name(),
            "email_template": self.parse_email_template(),
            "agent_label": self.parse_agent_label(),
            "jdk": self.parse_jdk(),
        }
        return config

    def parse_description(self) -> str:
        """Extract job description."""
        desc_el = self.root.find("description")
        text = desc_el.text if desc_el is not None and desc_el.text else ""
        logger.info(f"[PARSE] Description: {len(text)} chars")
        return text

    def parse_agent_label(self) -> str:
        """Extract agent label expression ('Restrict where this project can be run').
        Only present when <canRoam>false</canRoam> (checkbox enabled)."""
        can_roam = self.root.find("canRoam")
        if can_roam is not None and can_roam.text == "false":
            node_el = self.root.find("assignedNode")
            if node_el is not None and node_el.text:
                logger.info(f"[PARSE] Agent label: '{node_el.text}'")
                return node_el.text
        logger.info("[PARSE] Agent label: not restricted (canRoam=true)")
        return ""

    def parse_jdk(self) -> str:
        """Extract configured JDK name."""
        jdk_el = self.root.find("jdk")
        if jdk_el is not None and jdk_el.text and jdk_el.text != "(System)":
            logger.info(f"[PARSE] JDK: '{jdk_el.text}'")
            return jdk_el.text
        logger.info("[PARSE] JDK: default (System)")
        return ""

    def parse_parameters(self) -> list:
        """Extract all parameter definitions."""
        params = []
        # Search for parameterDefinitions in properties
        for prop in self.root.iter("parameterDefinitions"):
            for idx, param_el in enumerate(prop):
                param = self._parse_single_parameter(param_el, idx)
                if param:
                    params.append(param)
        logger.info(f"[PARSE] Parameters: {len(params)} found")
        return params

    def _parse_single_parameter(self, el: ET.Element, idx: int) -> Optional[dict]:
        """Parse a single parameter element."""
        tag = el.tag
        param_type = PARAM_TYPE_MAP.get(tag, "")

        # Boolean / String / Choice parameters
        if "BooleanParameterDefinition" in tag:
            param_type = "boolean"
        elif "TextParameterDefinition" in tag:
            param_type = "text"
        elif "StringParameterDefinition" in tag:
            param_type = "string"
        elif "ChoiceParameterDefinition" in tag:
            param_type = "choice"

        if not param_type:
            # Try to detect from known patterns
            for key, val in PARAM_TYPE_MAP.items():
                if key.split(".")[-1] in tag:
                    param_type = val
                    break
            if not param_type:
                param_type = "unknown"

        name_el = el.find("name")
        name = name_el.text if name_el is not None and name_el.text else f"UNKNOWN_{idx}"

        desc_el = el.find("description")
        description = desc_el.text if desc_el is not None and desc_el.text else ""

        # Script
        script = ""
        script_el = el.find(".//script/secureScript/script")
        if script_el is None:
            script_el = el.find(".//script/script")
        if script_el is None:
            script_el = el.find(".//groovyScript/secureScript/script")
        if script_el is None:
            script_el = el.find(".//groovyScript/script")
        if script_el is not None and script_el.text:
            script = script_el.text

        # Fallback script
        fallback = ""
        fb_el = el.find(".//script/secureFallbackScript/script")
        if fb_el is None:
            fb_el = el.find(".//script/fallbackScript/script")
        if fb_el is None:
            fb_el = el.find(".//groovyScript/secureFallbackScript/script")
        if fb_el is None:
            fb_el = el.find(".//groovyScript/fallbackScript/script")
        if fb_el is not None and fb_el.text:
            fallback = fb_el.text

        # Choice type
        choice_type_el = el.find("choiceType")
        choice_type = choice_type_el.text if choice_type_el is not None and choice_type_el.text else ""

        # Referenced parameters
        ref_el = el.find("referencedParameters")
        referenced = ref_el.text if ref_el is not None and ref_el.text else ""

        # Sandbox
        sandbox_el = el.find(".//secureScript/sandbox")
        if sandbox_el is None:
            sandbox_el = el.find(".//script/secureScript/sandbox")
        sandbox = sandbox_el.text if sandbox_el is not None and sandbox_el.text else ""

        # Filterable
        filterable_el = el.find("filterable")
        filterable = filterable_el.text if filterable_el is not None and filterable_el.text else ""

        # Visible item count
        vis_el = el.find("visibleItemCount")
        visible_count = vis_el.text if vis_el is not None and vis_el.text else ""

        # Default value (Boolean/String params)
        default_el = el.find("defaultValue")
        default_value = default_el.text if default_el is not None and default_el.text else ""

        # Choices (ChoiceParameterDefinition)
        choices = []
        choices_el = el.find(".//choices/a")
        if choices_el is not None:
            choices = [s.text for s in choices_el.findall("string") if s.text]

        logger.info(f"[PARSE]   Param #{idx}: {name} ({param_type})")
        return {
            "index": idx,
            "name": name,
            "type": param_type,
            "description": description,
            "script": script,
            "fallback_script": fallback,
            "choice_type": choice_type,
            "referenced_parameters": referenced,
            "sandbox": sandbox,
            "filterable": filterable,
            "visible_item_count": visible_count,
            "default_value": default_value,
            "choices": choices,
        }

    def parse_inject_variables(self) -> str:
        """Extract EnvInject Groovy script from multiple possible paths."""
        paths = [
            ".//EnvInjectBuildWrapper/info/secureGroovyScript/script",
            ".//EnvInjectBuildWrapper/info/groovyScriptContent",
            ".//EnvInjectJobProperty/info/secureGroovyScript/script",
            ".//EnvInjectJobProperty/info/groovyScriptContent",
        ]
        for xpath in paths:
            el = self.root.find(xpath)
            if el is not None and el.text:
                logger.info(f"[PARSE] InjectVariables found at: {xpath} ({len(el.text)} chars)")
                return el.text

        # Exhaustive search
        for el in self.root.iter("script"):
            parent = None
            # walk tree to find parent context
            for p in self.root.iter():
                if el in list(p):
                    parent = p
                    break
            if parent is not None and "EnvInject" in (parent.tag or ""):
                if el.text:
                    logger.info(f"[PARSE] InjectVariables found via iter() ({len(el.text)} chars)")
                    return el.text

        for el in self.root.iter("groovyScriptContent"):
            if el.text:
                logger.info(f"[PARSE] InjectVariables found via iter(groovyScriptContent)")
                return el.text

        logger.info("[PARSE] InjectVariables: not found")
        return ""

    def parse_build_steps(self) -> list:
        """Extract shell build step commands."""
        steps = []
        for shell in self.root.iter("hudson.tasks.Shell"):
            cmd_el = shell.find("command")
            if cmd_el is not None and cmd_el.text:
                steps.append(cmd_el.text)
        logger.info(f"[PARSE] Build steps: {len(steps)} found")
        return steps

    def parse_build_name(self) -> str:
        """Extract Build Name Setter template."""
        # Try multiple known paths
        for path in [
            ".//org.jenkinsci.plugins.buildnameupdater.BuildNameUpdater/buildName",
            ".//org.jenkinsci.plugins.buildnamesetter.BuildNameSetter/template",
            ".//jenkins.plugins.build__name__setter.BuildNameSetter/template",
        ]:
            el = self.root.find(path)
            if el is not None and el.text:
                logger.info(f"[PARSE] BuildName: '{el.text}'")
                return el.text

        # Iter search
        for el in self.root.iter("buildName"):
            if el.text:
                logger.info(f"[PARSE] BuildName (iter): '{el.text}'")
                return el.text
        for el in self.root.iter("template"):
            parent = None
            for p in self.root.iter():
                if el in list(p):
                    parent = p
                    break
            if parent is not None and "uild" in parent.tag and "ame" in parent.tag:
                if el.text:
                    return el.text

        logger.info("[PARSE] BuildName: not found")
        return ""

    def parse_email_template(self) -> str:
        """Extract Extended Email Publisher default content."""
        el = self.root.find(".//hudson.plugins.emailext.ExtendedEmailPublisher/defaultContent")
        if el is not None and el.text:
            logger.info(f"[PARSE] EmailTemplate: {len(el.text)} chars")
            return el.text
        logger.info("[PARSE] EmailTemplate: not found")
        return ""


# --- Template Generator ---

class TemplateGenerator:
    """Generates template XML by replacing content sections with placeholders."""

    def __init__(self, xml_text: str, config: dict,
                 source_url: str = "", job_name: str = "", extracted_at: str = ""):
        self.xml_text = xml_text
        self.config = config
        self.source_url = source_url
        self.job_name = job_name
        self.extracted_at = extracted_at or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    def _replace(self, text: str, content: str, placeholder: str) -> str:
        """Replace content in text, trying both raw and XML-escaped forms."""
        if not content:
            return text
        # Skip replacement if content is only whitespace (e.g. a single newline)
        # to avoid matching arbitrary whitespace positions in the XML
        if not content.strip():
            return text
        # Try direct replacement first
        if content in text:
            return text.replace(content, placeholder, 1)
        # Try XML-escaped form
        import html
        escaped = html.escape(content, quote=False)
        if escaped in text:
            return text.replace(escaped, placeholder, 1)
        return text

    def generate(self) -> str:
        """Generate template with placeholders and prepend HYDRA:META header."""
        result = self.xml_text

        # Try to extract job_version from XML (e.g. <version> child of root)
        job_version = ""
        try:
            root_el = ET.fromstring(normalize_xml_declaration(result))
            ver_el = root_el.find("version")
            if ver_el is not None and ver_el.text:
                job_version = ver_el.text.strip()
        except Exception:
            pass

        # Description
        result = self._replace(result, self.config.get("description", ""), PLACEHOLDER_DESCRIPTION)

        # Inject Variables
        result = self._replace(result, self.config.get("inject_variables", ""), PLACEHOLDER_INJECT_GROOVY)

        # Build Name
        result = self._replace(result, self.config.get("build_name", ""), PLACEHOLDER_BUILD_NAME)

        # Email Template
        result = self._replace(result, self.config.get("email_template", ""), PLACEHOLDER_EMAIL_TEMPLATE)

        # Parameters (scripts and fallbacks)
        for param in self.config.get("parameters", []):
            result = self._replace(result, param.get("script", ""), PLACEHOLDER_PARAM_SCRIPT)
            result = self._replace(result, param.get("fallback_script", ""), PLACEHOLDER_PARAM_FALLBACK)

        # Build Steps
        for step in self.config.get("build_steps", []):
            result = self._replace(result, step, PLACEHOLDER_BUILD_STEP)

        # Prepend HYDRA:META header (after the <?xml ...?> declaration if present)
        meta_block = build_template_meta(
            source_url=self.source_url,
            job_name=self.job_name,
            extracted_at=self.extracted_at,
            job_version=job_version,
        )
        # Insert after the XML declaration line, if present
        xml_decl_re = re.compile(r'(<\?xml[^?]*\?>)\s*\n?')
        m = xml_decl_re.match(result)
        if m:
            result = m.group(0) + meta_block + result[m.end():]
        else:
            result = meta_block + result

        logger.info("[TEMPLATE] Generated template with placeholders and HYDRA:META header")
        return result


# --- File Writer (Save to Repo) ---

class RepoWriter:
    """Writes parsed config sections to individual files in repo structure."""

    def __init__(self, base_dir: str, job_name: str, settings: dict):
        self.job_dir = os.path.join(base_dir, job_name)
        self.job_name = job_name
        self.settings = settings
        self.params_dir = os.path.join(self.job_dir, settings.get("parameters_dir", "Parameters"))
        self.launchers_dir = os.path.join(self.job_dir, settings.get("launchers_dir", "ScriptLauncher"))
        # Job prefix: job name
        self.prefix = job_name

    def write_all(self, config: dict, sections: dict):
        """Write all enabled sections to files."""
        os.makedirs(self.job_dir, exist_ok=True)

        if sections.get("description", True):
            self._write_description(config.get("description", ""))

        if sections.get("parameters", True):
            self._write_parameters(config.get("parameters", []))

        if sections.get("inject", True):
            self._write_inject(config.get("inject_variables", ""))

        if sections.get("build_steps", True):
            self._write_build_steps(config.get("build_steps", []))

        if sections.get("build_name", True):
            self._write_build_name(config.get("build_name", ""))

        if sections.get("email", True):
            self._write_email(config.get("email_template", ""))

        logger.info(f"[SAVE] All sections written to {self.job_dir}")

    def _write_file(self, path: str, content: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"[SAVE] Written: {os.path.basename(path)}")

    def _write_description(self, text: str):
        path = os.path.join(self.job_dir, f"{self.prefix}-Description.html")
        self._write_file(path, text)

    def _write_inject(self, text: str):
        path = os.path.join(self.job_dir, f"{self.prefix}-InjectVariables.groovy")
        self._write_file(path, text)

    def _write_build_name(self, text: str):
        path = os.path.join(self.job_dir, "BuildNameSetter_Template.txt")
        self._write_file(path, text)

    def _write_email(self, text: str):
        path = os.path.join(self.job_dir, "email_template.html")
        self._write_file(path, text)

    def _write_parameters(self, params: list):
        os.makedirs(self.params_dir, exist_ok=True)
        for param in params:
            idx = param["index"]
            name = param["name"]
            prefix = f"{idx:02d}-{name}"

            # Description file with config header
            header = self._build_param_header(param)
            desc = param.get("description", "")
            # Strip any existing headers from description (avoid duplicates)
            desc = re.sub(r"<!--\s*\n?Parameter Configuration:\n.+?-->\s*\n?", "", desc, flags=re.DOTALL)
            desc = desc.lstrip("\n")
            desc_content = header + desc
            desc_path = os.path.join(self.params_dir, f"{prefix}-Description.html")
            self._write_file(desc_path, desc_content)

            # Script
            script = param.get("script", "")
            if script:
                script_path = os.path.join(self.params_dir, f"{prefix}-Script.groovy")
                self._write_file(script_path, script)

            # Fallback
            fallback = param.get("fallback_script", "")
            if fallback:
                fb_path = os.path.join(self.params_dir, f"{prefix}-FallbackScript.groovy")
                self._write_file(fb_path, fallback)

    def _build_param_header(self, param: dict) -> str:
        ptype = param.get("type", "unknown")
        choice = param.get("choice_type", "")
        refs = param.get("referenced_parameters", "")
        sandbox = param.get("sandbox", "")
        filterable = param.get("filterable", "")
        visible_count = param.get("visible_item_count", "")
        default_value = param.get("default_value", "")

        # Human-readable type
        type_labels = {
            "active_choices": "Active Choices Parameter",
            "active_choices_reactive": "Active Choices Reactive Parameter",
            "active_choices_reactive_reference": "Active Choices Reactive Reference Parameter",
            "boolean": "Boolean Parameter",
            "string": "String Parameter",
            "text": "Text Parameter",
            "choice": "Choice Parameter",
        }
        type_label = type_labels.get(ptype, ptype)

        # Choice type label
        choice_labels = {
            "PT_SINGLE_SELECT": "Single Select",
            "PT_MULTI_SELECT": "Multi Select",
            "PT_CHECKBOX": "Checkbox",
            "PT_RADIO": "Radio Buttons",
            "PT_FORMATTED_HTML": "Formatted HTML",
            "PT_FORMATTED_HIDDEN_HTML": "Formatted Hidden HTML",
            "ET_FORMATTED_HTML": "Formatted HTML",
            "ET_FORMATTED_HIDDEN_HTML": "Formatted Hidden HTML",
        }
        choice_label = choice_labels.get(choice, choice)

        lines = ["<!--", "Parameter Configuration:"]
        lines.append(f"- Name: {param.get('name', '')}")
        lines.append(f"- Parameter Type: {type_label}")
        if choice_label:
            lines.append(f"- Choice Type: {choice_label}")
        if param.get("choices"):
            lines.append(f"- Choices: {', '.join(param['choices'])}")
        lines.append(f"- Referenced parameters: {refs if refs else 'none'}")
        lines.append(f"- Sandbox: {sandbox if sandbox else 'true'}")
        if filterable:
            lines.append(f"- Filterable: {filterable}")
        if visible_count:
            lines.append(f"- Visible Items: {visible_count}")
        if default_value:
            lines.append(f"- Default Value: {default_value}")
        lines.append("-->")
        lines.append("")
        return "\n".join(lines)

    def _write_build_steps(self, steps: list):
        os.makedirs(self.launchers_dir, exist_ok=True)
        for idx, step in enumerate(steps):
            # Try to extract script name from comment
            script_name = self._extract_script_name(step)
            if not script_name:
                script_name = f"Step{idx}"
            filename = f"{idx:02d}.{script_name}_Launcher.sh"
            path = os.path.join(self.launchers_dir, filename)
            self._write_file(path, step)

    def _extract_script_name(self, content: str) -> str:
        """Extract script name from '# Script Name: XXX' comment."""
        match = re.search(r"#\s*Script\s*Name:\s*(.+)", content, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            # Sanitize
            name = re.sub(r"[^\w\-.]", "_", name)
            return name
        return ""


# --- File Reader (Read Repo) ---

class RepoReader:
    """Reads config sections from repo file structure."""

    def __init__(self, base_dir: str, job_name: str, settings: dict):
        self.job_dir = os.path.join(base_dir, job_name)
        self.job_name = job_name
        self.settings = settings
        self.params_dir = os.path.join(self.job_dir, settings.get("parameters_dir", "Parameters"))
        self.launchers_dir = os.path.join(self.job_dir, settings.get("launchers_dir", "ScriptLauncher"))
        self.prefix = job_name
        self._warn_dir_mismatch(self.job_dir, self.params_dir, settings.get("parameters_dir", "Parameters"))
        self._warn_dir_mismatch(self.job_dir, self.launchers_dir, settings.get("launchers_dir", "ScriptLauncher"))

    def _warn_dir_mismatch(self, parent: str, full_path: str, configured_name: str):
        """Warn if the configured directory name doesn't exist but a case-similar one does."""
        if os.path.isdir(full_path):
            return  # all good
        if not os.path.isdir(parent):
            return  # parent missing, different problem
        actual_names = os.listdir(parent)
        for actual in actual_names:
            if actual.lower() == configured_name.lower() and actual != configured_name:
                logger.warning(
                    f"[READ] ⚠ Directory name mismatch: settings has '{configured_name}' "
                    f"but on disk it is '{actual}' — update 'launchers_dir'/'parameters_dir' in Settings."
                )
                return

    def read_all(self, sections: dict) -> dict:
        """Read all enabled sections from files."""
        config = {
            "description": "",
            "parameters": [],
            "inject_variables": "",
            "build_steps": [],
            "build_name": "",
            "email_template": "",
        }

        if sections.get("description", True):
            config["description"] = self._read_description()

        if sections.get("parameters", True):
            config["parameters"] = self._read_parameters()

        if sections.get("inject", True):
            config["inject_variables"] = self._read_inject()

        if sections.get("build_steps", True):
            config["build_steps"] = self._read_build_steps()

        if sections.get("build_name", True):
            config["build_name"] = self._read_build_name()

        if sections.get("email", True):
            config["email_template"] = self._read_email()

        logger.info(f"[READ] All sections read from {self.job_dir}")
        return config

    def _read_file(self, path: str) -> str:
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        return ""

    def _read_description(self) -> str:
        path = os.path.join(self.job_dir, f"{self.prefix}-Description.html")
        return self._read_file(path)

    def _read_inject(self) -> str:
        path = os.path.join(self.job_dir, f"{self.prefix}-InjectVariables.groovy")
        return self._read_file(path)

    def _read_build_name(self) -> str:
        path = os.path.join(self.job_dir, "BuildNameSetter_Template.txt")
        return self._read_file(path)

    def _read_email(self) -> str:
        path = os.path.join(self.job_dir, "email_template.html")
        return self._read_file(path)

    def _read_parameters(self) -> list:
        """Read parameters from files matching NN-NAME-Suffix pattern."""
        params = []
        if not os.path.isdir(self.params_dir):
            return params

        files = sorted(os.listdir(self.params_dir))
        # Group by NN-NAME prefix
        # Known suffixes — must match exactly at end of filename
        KNOWN_SUFFIXES = ["Description.html", "Script.groovy", "FallbackScript.groovy"]
        groups = {}
        for fname in files:
            # Match index and the rest: NN-<anything>
            match = re.match(r"^(\d+)-(.+)$", fname)
            if not match:
                continue
            idx_str = match.group(1)
            remainder = match.group(2)   # e.g. "REMOTE_CONFIG_SERVER_AND_FILE-Description.html"

            # Identify the suffix by checking known endings
            suffix = None
            name = None
            for ks in KNOWN_SUFFIXES:
                if remainder.endswith("-" + ks):
                    suffix = ks
                    name = remainder[: -(len(ks) + 1)]  # strip "-<suffix>"
                    break

            if suffix is None or name is None:
                continue  # skip files that don't match a known suffix

            key = (int(idx_str), name)
            if key not in groups:
                groups[key] = {}
            groups[key][suffix] = fname

        for (idx, name), suffixes in sorted(groups.items()):
            param = {"index": idx, "name": name, "type": "unknown", "description": "",
                     "script": "", "fallback_script": "", "choice_type": "", "referenced_parameters": ""}

            # Read description and parse header
            desc_file = suffixes.get("Description.html", "")
            if desc_file:
                raw = self._read_file(os.path.join(self.params_dir, desc_file))
                param["description"], meta = self._parse_param_header(raw)
                param.update(meta)

            # Read script
            script_file = suffixes.get("Script.groovy", "")
            if script_file:
                param["script"] = self._read_file(os.path.join(self.params_dir, script_file))

            # Read fallback
            fb_file = suffixes.get("FallbackScript.groovy", "")
            if fb_file:
                param["fallback_script"] = self._read_file(os.path.join(self.params_dir, fb_file))

            params.append(param)
            logger.info(f"[READ]   Param #{idx}: {name}")

        return params

    def _parse_param_header(self, content: str) -> tuple:
        """Separate header comment from actual description content. Returns (desc, meta_dict)."""
        meta = {}
        # Check for header
        match = re.match(r"<!--\s*\nParameter Configuration:\n(.+?)-->\s*\n?(.*)",
                         content, re.DOTALL)
        if not match:
            return content, meta

        header_body = match.group(1)
        desc = match.group(2)

        # Strip any duplicate headers from the description
        desc = re.sub(r"<!--\s*\n?Parameter Configuration:\n.+?-->\s*\n?", "", desc, flags=re.DOTALL)
        desc = desc.lstrip("\n")

        # Parse type
        type_match = re.search(r"Parameter Type:\s*(.+)", header_body)
        if type_match:
            type_str = type_match.group(1).strip()
            # Reverse lookup
            type_reverse = {
                "Active Choices Parameter": "active_choices",
                "Active Choices Reactive Parameter": "active_choices_reactive",
                "Active Choices Reactive Reference Parameter": "active_choices_reactive_reference",
                "Boolean Parameter": "boolean",
                "String Parameter": "string",
                "Text Parameter": "text",
                "Choice Parameter": "choice",
            }
            meta["type"] = type_reverse.get(type_str, type_str)

        # Choice type
        choice_match = re.search(r"Choice Type:\s*(.+)", header_body)
        if choice_match:
            label = choice_match.group(1).strip()
            # If already a raw value (PT_*, ET_*), keep as-is
            if label.startswith("PT_") or label.startswith("ET_"):
                meta["choice_type"] = label
            else:
                param_type = meta.get("type", "")
                is_reference = (param_type == "active_choices_reactive_reference")
                choice_reverse = {
                    "Single Select":         "PT_SINGLE_SELECT",
                    "Multi Select":          "PT_MULTI_SELECT",
                    "Checkbox":              "PT_CHECKBOX",
                    "Radio":                 "PT_RADIO",
                    "Radio Buttons":         "PT_RADIO",
                    # Formatted HTML: ET_ for DynamicReferenceParameter, PT_ for CascadeChoiceParameter
                    "Formatted HTML":        "ET_FORMATTED_HTML" if is_reference else "PT_FORMATTED_HTML",
                    "Formatted Hidden HTML": "ET_FORMATTED_HIDDEN_HTML" if is_reference else "PT_FORMATTED_HIDDEN_HTML",
                }
                meta["choice_type"] = choice_reverse.get(label, label)

        # Referenced parameters
        ref_match = re.search(r"Referenced parameters:\s*(.+)", header_body)
        if ref_match:
            val = ref_match.group(1).strip()
            if val.lower() != "none":
                meta["referenced_parameters"] = val

        # Sandbox
        sandbox_match = re.search(r"Sandbox:\s*(.+)", header_body)
        if sandbox_match:
            meta["sandbox"] = sandbox_match.group(1).strip()

        # Filterable
        filterable_match = re.search(r"Filterable:\s*(.+)", header_body)
        if filterable_match:
            meta["filterable"] = filterable_match.group(1).strip()

        # Visible Items
        vis_match = re.search(r"Visible Items:\s*(.+)", header_body)
        if vis_match:
            meta["visible_item_count"] = vis_match.group(1).strip()

        # Default Value (may be multiline for Text parameters — captures until next "- " field or end)
        default_match = re.search(r"Default Value:\s*(.+?)(?=\n- [A-Z]|\Z)", header_body, re.DOTALL)
        if default_match:
            meta["default_value"] = default_match.group(1).strip()

        # Choices (comma-separated list)
        choices_match = re.search(r"Choices:\s*(.+)", header_body)
        if choices_match:
            meta["choices"] = [c.strip() for c in choices_match.group(1).split(",")]

        return desc, meta

    def _read_build_steps(self) -> list:
        """Read launcher scripts sorted by filename."""
        steps = []
        if not os.path.isdir(self.launchers_dir):
            logger.warning(f"[READ] ⚠ Launchers dir not found: {self.launchers_dir}")
            # Suggest similarly named directories
            parent = os.path.dirname(self.launchers_dir)
            expected = os.path.basename(self.launchers_dir)
            if os.path.isdir(parent):
                candidates = [d for d in os.listdir(parent)
                              if os.path.isdir(os.path.join(parent, d))
                              and d.lower() != expected.lower()
                              and sum(c in expected.lower() for c in d.lower()) > len(expected) * 0.6]
                if candidates:
                    logger.warning(f"[READ]   Did you mean one of: {candidates}? "
                                   f"Check 'launchers_dir' in settings.")
            return steps
        files = sorted(f for f in os.listdir(self.launchers_dir) if f.endswith(".sh"))
        for fname in files:
            content = self._read_file(os.path.join(self.launchers_dir, fname))
            if content:
                steps.append(content)
        logger.info(f"[READ] Build steps: {len(steps)} files")
        return steps


# --- Config Generator (merge template + sections) ---

class ConfigGenerator:
    """Merges template with section content to produce full config.xml."""

    def __init__(self, template_path: str):
        self.template_path = template_path

    @staticmethod
    def _xml_escape(text: str) -> str:
        """Escape XML special characters in text content (for insertion inside XML elements)."""
        if not text:
            return text
        # Order matters: & must be first
        text = text.replace("&", "&amp;")
        text = text.replace("<", "&lt;")
        text = text.replace(">", "&gt;")
        return text

    def generate(self, config: dict, full_repo_config: dict = None,
                 original_config: dict = None) -> str:
        """Generate full config.xml from template + config dict.

        Args:
            config: Filtered config (only GUI-selected items from repo)
            full_repo_config: All items present in repo (before GUI deselection).
                             If provided, enables smart removal of deleted items.
            original_config: Original config parsed from Jenkins raw_xml.
                            Used to restore content for deselected items.
        """
        if not os.path.isfile(self.template_path):
            raise FileNotFoundError(f"Template not found: {self.template_path}")

        with open(self.template_path, "r", encoding="utf-8") as f:
            xml_text = f.read()

        # --- Update HYDRA:META: overwrite with merged_at timestamp ---
        original_meta = parse_template_meta(xml_text)
        merged_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        new_meta_block = build_merged_meta(original_meta, merged_at)
        if _TEMPLATE_META_RE.search(xml_text):
            xml_text = _TEMPLATE_META_RE.sub(new_meta_block, xml_text, count=1)
            logger.debug("[GENERATE] HYDRA:META header updated with merged_at timestamp")
        else:
            logger.debug("[GENERATE] No HYDRA:META header found in template — skipping meta update")

        if full_repo_config is not None:
            # Smart mode: remove deleted blocks first (template is still valid XML),
            # then replace all placeholders
            logger.debug("[GENERATE] Smart mode: analyzing template for deletions/deselections")
            xml_text = self._remove_deleted_blocks(xml_text, config, full_repo_config)
            xml_text = self._smart_replace_params(xml_text, config, full_repo_config, original_config)
            xml_text = self._smart_replace_steps(xml_text, config, full_repo_config, original_config)

        # Replace simple placeholders (after smart processing to keep XML valid for ET)
        # For each section: try placeholder first, fall back to direct tag content replacement
        simple_sections = [
            (PLACEHOLDER_DESCRIPTION, "description", "description"),
            (PLACEHOLDER_INJECT_GROOVY, "inject_variables", None),
            (PLACEHOLDER_BUILD_NAME, "build_name", None),
            (PLACEHOLDER_EMAIL_TEMPLATE, "email_template", "defaultContent"),
        ]
        for placeholder, config_key, tag_name in simple_sections:
            content = config.get(config_key, "")
            if not content:
                continue
            if placeholder in xml_text:
                xml_text = xml_text.replace(placeholder, self._xml_escape(content), 1)
                logger.debug(f"[GENERATE] {config_key}: replaced placeholder ({len(content)} chars)")
            elif tag_name:
                # Placeholder missing — replace tag content directly via regex
                pattern = re.compile(
                    rf'(<{re.escape(tag_name)}>)(.*?)(</{re.escape(tag_name)}>)',
                    re.DOTALL
                )
                new_content = self._xml_escape(content)
                # Use lambda to avoid regex interpretation of backslashes in content
                xml_text, n = pattern.subn(
                    lambda m: m.group(1) + new_content + m.group(3), xml_text, count=1
                )
                if n:
                    logger.info(f"[GENERATE] {config_key}: replaced <{tag_name}> content directly "
                                f"(no placeholder, {len(content)} chars)")
                else:
                    logger.warning(f"[GENERATE] {config_key}: no placeholder and <{tag_name}> tag "
                                   f"not found — content NOT applied")

        if full_repo_config is None:
            # Legacy mode: sequential replacement (only for params with scripts)
            for param in config.get("parameters", []):
                script = param.get("script", "")
                fallback = param.get("fallback_script", "")
                if script or fallback:
                    xml_text = xml_text.replace(PLACEHOLDER_PARAM_SCRIPT,
                                               self._xml_escape(script), 1)
                    xml_text = xml_text.replace(PLACEHOLDER_PARAM_FALLBACK,
                                               self._xml_escape(fallback), 1)
            for step in config.get("build_steps", []):
                xml_text = xml_text.replace(PLACEHOLDER_BUILD_STEP,
                                            self._xml_escape(step), 1)

        # Normalize before return
        xml_text = normalize_xml_declaration(xml_text)
        logger.info("[GENERATE] Config XML generated from template")
        return xml_text

    def _remove_deleted_blocks(self, xml_text: str, config: dict, full_repo_config: dict) -> str:
        """Remove XML blocks for items deleted from repo (before placeholder substitution).
        Uses ET to identify what to remove, then regex on original text for removal."""
        repo_param_names = {p["name"] for p in full_repo_config.get("parameters", [])}
        num_repo_steps = len(full_repo_config.get("build_steps", []))

        try:
            normalized = normalize_xml_declaration(xml_text)
            root = ET.fromstring(normalized)
        except ET.ParseError as e:
            logger.error(f"[GENERATE] XML parse failed for block removal: {e}")
            return xml_text

        # Identify deleted parameter names
        param_defs = root.find(".//parameterDefinitions")
        params_to_remove = []
        if param_defs is not None:
            for child in list(param_defs):
                name_el = child.find("name")
                if name_el is not None and name_el.text and name_el.text not in repo_param_names:
                    params_to_remove.append(name_el.text)

        if params_to_remove:
            logger.info(f"[GENERATE] Parameters to remove (deleted from repo): {params_to_remove}")
        else:
            logger.debug("[GENERATE] No parameters to remove — all template params present in repo")

        # Remove deleted parameter blocks using regex
        for name in params_to_remove:
            xml_text = self._remove_element_containing_name(xml_text, name)

        # Remove deleted build step blocks (excess beyond repo count)
        total_step_blocks = xml_text.count('<hudson.tasks.Shell>')
        excess = total_step_blocks - num_repo_steps
        if excess > 0:
            logger.info(f"[GENERATE] Build steps to remove: {excess} "
                        f"(template has {total_step_blocks}, repo has {num_repo_steps})")
            for _ in range(excess):
                m = None
                for m in re.finditer(
                    r'\s*<hudson\.tasks\.Shell>.*?</hudson\.tasks\.Shell>',
                    xml_text, re.DOTALL
                ):
                    pass  # iterate to last match
                if m:
                    xml_text = xml_text[:m.start()] + xml_text[m.end():]
                    logger.debug("[GENERATE] Removed last build step block")
        else:
            logger.debug(f"[GENERATE] No build steps to remove — "
                         f"template has {total_step_blocks}, repo has {num_repo_steps}")

        return xml_text

    def _remove_element_containing_name(self, xml_text: str, param_name: str) -> str:
        """Remove the XML element block that directly contains <name>param_name</name>."""
        name_pattern = f'<name>{re.escape(param_name)}</name>'
        name_match = re.search(name_pattern, xml_text)
        if not name_match:
            logger.warning(f"[GENERATE] Cannot remove '{param_name}': <name> tag not found in XML")
            return xml_text

        pos = name_match.start()

        # Search backwards for the opening tag — it must be the closest parameter-type
        # opening tag that is NOT closed before reaching our <name> line
        before = xml_text[:pos]

        # Find all parameter-type opening tags before this name
        open_pattern = re.compile(
            r'(\s*<((?:org\.biouno\.unochoice\.\w+|hudson\.model\.\w+ParameterDefinition))[^>]*>)'
        )
        open_matches = list(open_pattern.finditer(before))
        if not open_matches:
            logger.warning(f"[GENERATE] Cannot remove '{param_name}': no enclosing parameter tag found")
            return xml_text

        # The correct opening tag is the last one whose closing tag appears AFTER our <name>
        # (i.e., it encloses our <name> element)
        for open_match in reversed(open_matches):
            tag_name = open_match.group(2)
            # Check if this tag's closing tag appears AFTER the <name>
            close_pattern = re.compile(rf'</{re.escape(tag_name)}>')
            # First closing tag of this type after the opening
            close_match = close_pattern.search(xml_text, open_match.end())
            if close_match and close_match.start() > name_match.end():
                # This opening tag encloses our <name> — this is the one
                block_start = open_match.start()
                block_end = close_match.end()
                # Consume trailing whitespace/newline
                if block_end < len(xml_text) and xml_text[block_end] == '\n':
                    block_end += 1
                logger.info(f"[GENERATE] Removed deleted parameter: {param_name} "
                            f"(tag: {tag_name.split('.')[-1]})")
                return xml_text[:block_start] + xml_text[block_end:]

        logger.warning(f"[GENERATE] Cannot remove '{param_name}': "
                       f"no enclosing tag with closing after <name> found")
        return xml_text

    def _smart_replace_params(self, xml_text: str, config: dict,
                              full_repo_config: dict, original_config: dict = None) -> str:
        """Replace param placeholders considering selected/deselected items.
        Deleted items have already been removed by _remove_deleted_blocks.

        For each placeholder position in the template:
        - If param is in config (selected from repo): replace with repo content
        - If param is in full_repo_config but not config (deselected): replace with original content
        """
        selected_names = {p["name"] for p in config.get("parameters", [])}
        repo_names = {p["name"] for p in full_repo_config.get("parameters", [])}

        # Build lookup dicts by name
        selected_by_name = {p["name"]: p for p in config.get("parameters", [])}
        original_by_name = {}
        if original_config:
            original_by_name = {p["name"]: p for p in original_config.get("parameters", [])}

        # Parse the XML (after removal, before content substitution — still valid XML)
        try:
            normalized = normalize_xml_declaration(xml_text)
            root = ET.fromstring(normalized)
        except ET.ParseError as e:
            logger.error(f"[GENERATE] XML parse failed in smart_replace_params: {e}")
            logger.warning("[GENERATE] Falling back to sequential replacement (no name matching)")
            for param in config.get("parameters", []):
                xml_text = xml_text.replace(PLACEHOLDER_PARAM_SCRIPT,
                                            self._xml_escape(param.get("script", "")), 1)
                xml_text = xml_text.replace(PLACEHOLDER_PARAM_FALLBACK,
                                            self._xml_escape(param.get("fallback_script", "")), 1)
            return xml_text

        # Find remaining parameters in template order (deleted ones already removed)
        param_defs_el = root.find(".//parameterDefinitions")
        if param_defs_el is None:
            # --- ADD mode: parameterDefinitions section missing from template ---
            selected_params = config.get("parameters", [])
            if not selected_params:
                logger.warning("[GENERATE] No <parameterDefinitions> in template and no params in repo — nothing to do")
                return xml_text

            logger.info(f"[GENERATE] No <parameterDefinitions> in template — ADD mode: "
                        f"injecting {len(selected_params)} parameters")
            new_blocks = []
            for p in selected_params:
                block = self._generate_param_xml(p)
                if block:
                    new_blocks.append(block)
                    logger.info(f"[GENERATE]   {p['name']}: ADD — generated XML block")
                else:
                    logger.warning(f"[GENERATE]   {p['name']}: ADD — could not generate XML block (type={p.get('type','')})")

            if new_blocks:
                param_section = (
                    "    <hudson.model.ParametersDefinitionProperty>\n"
                    "      <parameterDefinitions>\n"
                    + "\n".join(new_blocks) + "\n"
                    "      </parameterDefinitions>\n"
                    "    </hudson.model.ParametersDefinitionProperty>"
                )
                # Try to insert inside <properties>...</properties>
                props_close = "</properties>"
                if props_close in xml_text:
                    xml_text = xml_text.replace(props_close, param_section + "\n  " + props_close, 1)
                    logger.info(f"[GENERATE] Injected parameterDefinitions section with {len(new_blocks)} params into <properties>")
                else:
                    logger.error("[GENERATE] Cannot inject params — no <properties> section found in template")
            return xml_text

        # Get ordered list of params whose script section contains a placeholder
        scripted_param_names = []
        for param_el in list(param_defs_el):
            name_el = param_el.find("name")
            if name_el is None or not name_el.text:
                continue
            pname = name_el.text
            # Check raw xml_text: does this param's section contain the placeholder?
            name_tag = f"<name>{pname}</name>"
            name_pos = xml_text.find(name_tag)
            if name_pos < 0:
                continue
            next_name_pos = xml_text.find("<name>", name_pos + len(name_tag))
            if next_name_pos < 0:
                next_name_pos = len(xml_text)
            if PLACEHOLDER_PARAM_SCRIPT in xml_text[name_pos:next_name_pos]:
                scripted_param_names.append(pname)

        logger.debug(f"[GENERATE] Scripted params in template order ({len(scripted_param_names)}): "
                     f"{scripted_param_names}")

        # Warn about repo params not found in template — and generate XML blocks for them
        template_names = {p for p in scripted_param_names}
        # Also include non-scripted template params
        all_template_names = set()
        # Map template param name -> XML tag (type)
        template_param_tags = {}
        for param_el in list(param_defs_el):
            name_el = param_el.find("name")
            if name_el is not None and name_el.text:
                all_template_names.add(name_el.text)
                template_param_tags[name_el.text] = param_el.tag

        # Determine which params need type change (remove old + regenerate)
        params_to_retype = []
        for pname in selected_names:
            if pname in all_template_names:
                p = selected_by_name[pname]
                repo_type = p.get("type", "")
                tpl_tag = template_param_tags.get(pname, "")
                # Map repo type to expected XML tag
                expected_tags = {
                    "active_choices": "org.biouno.unochoice.ChoiceParameter",
                    "active_choices_reactive": "org.biouno.unochoice.CascadeChoiceParameter",
                    "active_choices_reactive_reference": "org.biouno.unochoice.DynamicReferenceParameter",
                    "boolean": "hudson.model.BooleanParameterDefinition",
                    "string": "hudson.model.StringParameterDefinition",
                    "text": "hudson.model.TextParameterDefinition",
                    "choice": "hudson.model.ChoiceParameterDefinition",
                }
                expected_tag = expected_tags.get(repo_type, "")
                if expected_tag and expected_tag != tpl_tag:
                    params_to_retype.append(pname)
                    logger.info(f"[GENERATE]   {pname}: TYPE CHANGED — "
                                f"{tpl_tag.split('.')[-1]} → {expected_tag.split('.')[-1]}")

        # Remove old blocks for retyped params and consume their placeholders
        for pname in params_to_retype:
            # Consume placeholder if this param had one
            if pname in template_names:
                xml_text = xml_text.replace(PLACEHOLDER_PARAM_SCRIPT, "", 1)
                xml_text = xml_text.replace(PLACEHOLDER_PARAM_FALLBACK, "", 1)
                scripted_param_names = [n for n in scripted_param_names if n != pname]
            xml_text = self._remove_element_containing_name(xml_text, pname)
            all_template_names.discard(pname)

        new_params_xml = []
        for pname in selected_names:
            if pname not in all_template_names:
                p = selected_by_name[pname]
                block = self._generate_param_xml(p)
                if block:
                    new_params_xml.append(block)
                    logger.info(f"[GENERATE]   {pname}: NEW — generated XML block for insertion")
                else:
                    logger.warning(f"[GENERATE]   {pname}: NEW — could not generate XML block")

        # Insert new parameter blocks before </parameterDefinitions>
        if new_params_xml:
            insert_marker = "</parameterDefinitions>"
            insert_content = "\n".join(new_params_xml) + "\n        "
            xml_text = xml_text.replace(insert_marker, insert_content + insert_marker, 1)

        # Replace placeholders in order
        for pname in scripted_param_names:
            if pname in selected_names:
                # Selected: replace with repo content
                p = selected_by_name[pname]
                xml_text = xml_text.replace(PLACEHOLDER_PARAM_SCRIPT,
                                            self._xml_escape(p.get("script", "")), 1)
                xml_text = xml_text.replace(PLACEHOLDER_PARAM_FALLBACK,
                                            self._xml_escape(p.get("fallback_script", "")), 1)
                logger.debug(f"[GENERATE]   {pname}: SELECTED — replaced with repo content "
                             f"(script: {len(p.get('script',''))} chars)")
            else:
                # Deselected (in repo but not selected): restore original content
                orig = original_by_name.get(pname, {})
                xml_text = xml_text.replace(PLACEHOLDER_PARAM_SCRIPT,
                                            self._xml_escape(orig.get("script", "")), 1)
                xml_text = xml_text.replace(PLACEHOLDER_PARAM_FALLBACK,
                                            self._xml_escape(orig.get("fallback_script", "")), 1)
                if orig.get("script"):
                    logger.debug(f"[GENERATE]   {pname}: DESELECTED — preserved original content "
                                 f"(script: {len(orig.get('script',''))} chars)")
                else:
                    logger.warning(f"[GENERATE]   {pname}: DESELECTED — no original content available "
                                   f"(script will be empty)")

        # Update parameter descriptions and sandbox for selected params in template
        for pname in selected_names:
            if pname in all_template_names:
                p = selected_by_name[pname]
                desc = p.get("description", "")
                if desc:
                    xml_text = self._replace_param_description(xml_text, pname, desc)
                # Update sandbox value
                sandbox = p.get("sandbox", "")
                if sandbox:
                    xml_text = self._replace_param_sandbox(xml_text, pname, sandbox)

        # Update inline scripts for params that had no placeholder (already had content in template)
        for pname in selected_names:
            if pname in all_template_names and pname not in scripted_param_names:
                p = selected_by_name[pname]
                script = p.get("script", "")
                fallback = p.get("fallback_script", "")
                sandbox = p.get("sandbox", "")
                if script:
                    xml_text = self._replace_param_script(xml_text, pname, script, fallback, sandbox)

        # Reorder parameters in the final XML according to repo index order
        xml_text = self._reorder_params_by_repo_index(xml_text, full_repo_config)

        return xml_text

    def _reorder_params_by_repo_index(self, xml_text: str, full_repo_config: dict) -> str:
        """Reorder parameter blocks inside <parameterDefinitions> to match repo index order.

        The repo index (prefix NN in filenames like 00-NAME, 01-NAME) defines the
        intended order of parameters in the Jenkins Job. This method extracts each
        parameter block and reorders them accordingly.
        """
        # Build name→index lookup from repo config
        repo_index_by_name = {}
        for p in full_repo_config.get("parameters", []):
            repo_index_by_name[p["name"]] = p.get("index", 999)

        # Find parameterDefinitions section boundaries
        pd_open = "<parameterDefinitions>"
        pd_close = "</parameterDefinitions>"
        pd_start = xml_text.find(pd_open)
        pd_end = xml_text.find(pd_close)
        if pd_start < 0 or pd_end < 0:
            return xml_text

        pd_content_start = pd_start + len(pd_open)
        inner = xml_text[pd_content_start:pd_end]

        # Extract individual parameter blocks with their names
        # Each block starts with whitespace + opening tag and ends with closing tag
        param_tags = [
            "org.biouno.unochoice.ChoiceParameter",
            "org.biouno.unochoice.CascadeChoiceParameter",
            "org.biouno.unochoice.DynamicReferenceParameter",
            "hudson.model.BooleanParameterDefinition",
            "hudson.model.StringParameterDefinition",
            "hudson.model.TextParameterDefinition",
            "hudson.model.ChoiceParameterDefinition",
        ]
        # Build regex that matches any parameter block
        tag_pattern = "|".join(re.escape(t) for t in param_tags)
        block_re = re.compile(
            rf'(\s*<({tag_pattern})\b[^>]*>.*?</\2>)',
            re.DOTALL
        )

        blocks = []
        for m in block_re.finditer(inner):
            block_text = m.group(1)
            # Extract parameter name from block
            name_match = re.search(r'<name>([^<]+)</name>', block_text)
            if name_match:
                pname = name_match.group(1)
                idx = repo_index_by_name.get(pname, 999)
                blocks.append((idx, pname, block_text))
            else:
                # No name found — keep at end
                blocks.append((9999, "", block_text))

        if not blocks:
            return xml_text

        # Check if already in correct order
        current_order = [b[0] for b in blocks]
        sorted_order = sorted(current_order)
        if current_order == sorted_order:
            logger.debug("[GENERATE] Parameters already in correct repo index order")
            return xml_text

        # Sort by repo index
        blocks.sort(key=lambda b: b[0])

        # Rebuild parameterDefinitions content
        new_inner = "\n".join(b[2] for b in blocks) + "\n      "

        # Replace in xml_text
        xml_text = xml_text[:pd_content_start] + "\n" + new_inner + xml_text[pd_end:]

        reordered = [(b[0], b[1]) for b in blocks]
        logger.info(f"[GENERATE] Parameters reordered by repo index: "
                    f"{[f'{idx}:{name}' for idx, name in reordered]}")

        return xml_text

    def _replace_param_script(self, xml_text: str, param_name: str,
                              new_script: str, new_fallback: str = "",
                              sandbox: str = "") -> str:
        """Replace inline script content of a parameter identified by name."""
        name_tag = f"<name>{re.escape(param_name)}</name>"
        name_match = re.search(name_tag, xml_text)
        if not name_match:
            return xml_text

        # Find the section for this param (up to next <name> or end)
        next_name = re.search(r"<name>", xml_text[name_match.end():])
        section_end = name_match.end() + next_name.start() if next_name else len(xml_text)

        section = xml_text[name_match.start():section_end]

        # Replace <secureScript>...<script>OLD</script> with new content
        # Handle both <script>content</script> and <script/> (empty self-closing)
        script_pattern = re.compile(
            r'(<secureScript[^>]*>\s*)(<script>.*?</script>|<script\s*/>)', re.DOTALL)
        matches = list(script_pattern.finditer(section))
        if matches:
            m = matches[0]
            replacement = m.group(1) + f"<script>{self._xml_escape(new_script)}</script>"
            new_section = section[:m.start()] + replacement + section[m.end():]
            section = new_section

        # Replace sandbox value if specified
        if sandbox:
            section = re.sub(
                r'(<secureScript[^>]*>\s*<script>.*?</script>\s*<sandbox>)(true|false)(</sandbox>)',
                rf'\g<1>{sandbox}\g<3>', section, count=1, flags=re.DOTALL)

        # Replace fallback script
        if new_fallback:
            fb_pattern = re.compile(
                r'(<secureFallbackScript[^>]*>\s*)(<script>.*?</script>|<script\s*/>)', re.DOTALL)
            fb_matches = list(fb_pattern.finditer(section))
            if fb_matches:
                m = fb_matches[0]
                replacement = m.group(1) + f"<script>{self._xml_escape(new_fallback)}</script>"
                section = section[:m.start()] + replacement + section[m.end():]

        xml_text = xml_text[:name_match.start()] + section + xml_text[section_end:]
        logger.debug(f"[GENERATE]   {param_name}: inline script updated ({len(new_script)} chars, sandbox={sandbox})")
        return xml_text

    def _replace_param_description(self, xml_text: str, param_name: str, new_desc: str) -> str:
        """Replace the <description> content of a specific parameter identified by name."""
        # Find <name>param_name</name> then the <description>...</description> that follows
        name_pattern = f'<name>{re.escape(param_name)}</name>'
        name_match = re.search(name_pattern, xml_text)
        if not name_match:
            return xml_text

        # Find <description>...</description> after <name>
        desc_pattern = re.compile(r'(<description>)(.*?)(</description>)', re.DOTALL)
        desc_match = desc_pattern.search(xml_text, name_match.end())
        if not desc_match:
            return xml_text

        # Make sure this description belongs to the same parameter (not a later one)
        # Check there's no other <name> between our name and this description
        between = xml_text[name_match.end():desc_match.start()]
        if '<name>' in between:
            return xml_text

        new_content = self._xml_escape(new_desc)
        xml_text = xml_text[:desc_match.start(2)] + new_content + xml_text[desc_match.end(2):]
        return xml_text

    def _replace_param_sandbox(self, xml_text: str, param_name: str, sandbox_val: str) -> str:
        """Replace the <sandbox> value in the secureScript section of a parameter."""
        name_tag = f"<name>{re.escape(param_name)}</name>"
        name_match = re.search(name_tag, xml_text)
        if not name_match:
            return xml_text
        next_name = re.search(r"<name>", xml_text[name_match.end():])
        section_end = name_match.end() + next_name.start() if next_name else len(xml_text)
        section = xml_text[name_match.start():section_end]
        # Replace first <sandbox>...</sandbox> after <secureScript> (not the fallback one)
        new_section = re.sub(
            r'(<secureScript[^>]*>.*?<sandbox>)(true|false)(</sandbox>)',
            rf'\g<1>{sandbox_val}\g<3>', section, count=1, flags=re.DOTALL)
        if new_section != section:
            xml_text = xml_text[:name_match.start()] + new_section + xml_text[section_end:]
        return xml_text

    def _smart_replace_steps(self, xml_text: str, config: dict,
                             full_repo_config: dict, original_config: dict = None) -> str:
        """Replace build step placeholders or inject new steps into <builders> if empty."""
        selected_steps = config.get("build_steps", [])
        repo_steps = full_repo_config.get("build_steps", [])
        original_steps = original_config.get("build_steps", []) if original_config else []

        total_slots = xml_text.count(PLACEHOLDER_BUILD_STEP)
        logger.debug(f"[GENERATE] Build steps: {total_slots} placeholder slots, "
                     f"{len(repo_steps)} in repo, {len(selected_steps)} selected")

        # --- NEW: inject into empty <builders> when template has no slots ---
        if total_slots == 0 and selected_steps:
            blocks = []
            for i, step in enumerate(selected_steps):
                blocks.append(
                    f"    <hudson.tasks.Shell>\n"
                    f"      <command>{self._xml_escape(step)}</command>\n"
                    f"      <configuredLocalRules/>\n"
                    f"    </hudson.tasks.Shell>"
                )
            insert_content = "\n" + "\n".join(blocks) + "\n  "
            xml_text = xml_text.replace("<builders>\n  </builders>",
                                        f"<builders>{insert_content}</builders>", 1)
            if "<builders>" in xml_text and insert_content not in xml_text:
                # fallback: replace any empty builders variant
                xml_text = re.sub(r'<builders\s*/>', f"<builders>{insert_content}</builders>", xml_text, count=1)
            logger.info(f"[GENERATE] Build steps: injected {len(selected_steps)} steps into empty <builders>")
            return xml_text

        # Build selected indices set
        selected_set = set()
        for s in selected_steps:
            for i, rs in enumerate(repo_steps):
                if rs == s and i not in selected_set:
                    selected_set.add(i)
                    break

        n_selected = 0
        n_deselected = 0
        for slot_idx in range(total_slots):
            if slot_idx < len(repo_steps):
                if slot_idx in selected_set:
                    xml_text = xml_text.replace(PLACEHOLDER_BUILD_STEP,
                                                self._xml_escape(repo_steps[slot_idx]), 1)
                    n_selected += 1
                else:
                    orig_content = original_steps[slot_idx] if slot_idx < len(original_steps) else ""
                    xml_text = xml_text.replace(PLACEHOLDER_BUILD_STEP,
                                                self._xml_escape(orig_content), 1)
                    n_deselected += 1
                    if not orig_content:
                        logger.warning(f"[GENERATE] Build step #{slot_idx}: DESELECTED but no original "
                                       f"content available — step will be empty")
            else:
                xml_text = xml_text.replace(PLACEHOLDER_BUILD_STEP, "", 1)
                logger.warning(f"[GENERATE] Build step #{slot_idx}: orphan placeholder removed (unexpected)")

        logger.debug(f"[GENERATE] Build steps result: {n_selected} updated from repo, "
                     f"{n_deselected} preserved original")
        return xml_text

    def _generate_param_xml(self, param: dict) -> str:
        """Generate an XML block for a new parameter (not in template)."""
        name = param.get("name", "")
        raw_script = param.get("script", "")
        raw_fallback = param.get("fallback_script", "")
        desc = self._xml_escape(param.get("description", ""))
        script = self._xml_escape(raw_script)
        fallback = self._xml_escape(raw_fallback)
        ptype = param.get("type", "")
        choice_type = param.get("choice_type", "")
        refs = param.get("referenced_parameters", "")

        # Map type to XML tag
        tag_map = {
            "active_choices": "org.biouno.unochoice.ChoiceParameter",
            "active_choices_reactive": "org.biouno.unochoice.CascadeChoiceParameter",
            "active_choices_reactive_reference": "org.biouno.unochoice.DynamicReferenceParameter",
        }

        # If has script but type is 'string' or unknown, infer from choice_type/content/refs
        if ptype not in tag_map and (raw_script or raw_fallback):
            if choice_type.startswith("ET_"):
                ptype = "active_choices_reactive_reference"
            elif refs:
                ptype = "active_choices_reactive"
            elif "<input" in raw_script or "return \"<" in raw_script or 'return """' in raw_script:
                # Script returns HTML → DynamicReferenceParameter
                ptype = "active_choices_reactive_reference"
                if not choice_type:
                    choice_type = "ET_FORMATTED_HTML"
            else:
                ptype = "active_choices"

        tag = tag_map.get(ptype)

        if tag:
            # Active Choices parameter
            import random
            random_name = f"choice-parameter-{random.randint(100000000000, 999999999999)}"
            filterable_val = param.get("filterable", "false") or "false"
            visible_count = param.get("visible_item_count", "1") or "1"

            filterable_xml = ""
            if "Cascade" in tag or tag.endswith("ChoiceParameter"):
                filterable_xml = (f"\n          <filterable>{filterable_val}</filterable>"
                                  f"\n          <filterLength>1</filterLength>")

            omit_value = ""
            if "DynamicReference" in tag:
                omit_value = "\n          <omitValueField>false</omitValueField>"

            refs_xml = f"<referencedParameters>{self._xml_escape(refs)}</referencedParameters>" if refs else "<referencedParameters/>"
            sandbox_val = param.get("sandbox", "false") or "false"

            return f"""        <{tag} plugin="uno-choice@2.8.3">
          <name>{self._xml_escape(name)}</name>
          <description>{desc}</description>
          <randomName>{random_name}</randomName>
          <visibleItemCount>{visible_count}</visibleItemCount>
          <script class="org.biouno.unochoice.model.GroovyScript">
            <secureScript plugin="script-security@1341.va_2819b_414686">
              <script>{script}</script>
              <sandbox>{sandbox_val}</sandbox>
            </secureScript>
            <secureFallbackScript plugin="script-security@1341.va_2819b_414686">
              <script>{fallback}</script>
              <sandbox>true</sandbox>
            </secureFallbackScript>
          </script>
          <parameters class="linked-hash-map"/>
          {refs_xml}
          <choiceType>{choice_type or 'PT_SINGLE_SELECT'}</choiceType>{filterable_xml}{omit_value}
        </{tag}>"""

        elif ptype == "boolean":
            default_val = param.get("default_value", "false") or "false"
            return f"""        <hudson.model.BooleanParameterDefinition>
          <name>{self._xml_escape(name)}</name>
          <description>{desc}</description>
          <defaultValue>{default_val}</defaultValue>
        </hudson.model.BooleanParameterDefinition>"""

        elif ptype == "string":
            default_val = self._xml_escape(param.get("default_value", ""))
            return f"""        <hudson.model.StringParameterDefinition>
          <name>{self._xml_escape(name)}</name>
          <description>{desc}</description>
          <defaultValue>{default_val}</defaultValue>
          <trim>false</trim>
        </hudson.model.StringParameterDefinition>"""

        elif ptype == "text":
            default_val = self._xml_escape(param.get("default_value", ""))
            return f"""        <hudson.model.TextParameterDefinition>
          <name>{self._xml_escape(name)}</name>
          <description>{desc}</description>
          <defaultValue>{default_val}</defaultValue>
          <trim>false</trim>
        </hudson.model.TextParameterDefinition>"""

        elif ptype == "choice":
            choices = param.get("choices", [])
            choices_xml = "\n".join(f"              <string>{self._xml_escape(c)}</string>"
                                   for c in choices)
            return f"""        <hudson.model.ChoiceParameterDefinition>
          <name>{self._xml_escape(name)}</name>
          <description>{desc}</description>
          <choices class="java.util.Arrays$ArrayList">
            <a class="string-array">
{choices_xml}
            </a>
          </choices>
        </hudson.model.ChoiceParameterDefinition>"""

        return ""

    def _remove_param_blocks(self, xml_text: str, names_to_remove: list) -> str:
        """Remove entire parameter XML blocks for deleted parameters by name.
        Uses ElementTree for reliable removal, then serializes back."""
        try:
            normalized = normalize_xml_declaration(xml_text)
            root = ET.fromstring(normalized)
            param_defs = root.find(".//parameterDefinitions")
            if param_defs is None:
                return xml_text
            names_set = set(names_to_remove)
            to_remove = []
            for child in list(param_defs):
                name_el = child.find("name")
                if name_el is not None and name_el.text in names_set:
                    to_remove.append(child)
            for el in to_remove:
                param_defs.remove(el)
                logger.info(f"[GENERATE] Removed parameter block: {el.find('name').text}")
            # Serialize back
            # Preserve XML declaration
            xml_decl = ""
            decl_match = re.match(r'(<\?xml[^?]*\?>)\s*', xml_text)
            if decl_match:
                xml_decl = decl_match.group(1) + "\n"
            body = ET.tostring(root, encoding="unicode")
            return xml_decl + body
        except ET.ParseError as e:
            logger.warning(f"[GENERATE] XML parse failed for removal, using regex fallback: {e}")
            # Regex fallback
            for name in names_to_remove:
                patterns = [
                    rf'\s*<org\.biouno\.unochoice\.\w+[^>]*>(?:(?!<org\.biouno\.unochoice\.).)*?<name>{re.escape(name)}</name>.*?</org\.biouno\.unochoice\.\w+>',
                    rf'\s*<hudson\.model\.\w+ParameterDefinition[^>]*>(?:(?!<hudson\.model\.).)*?<name>{re.escape(name)}</name>.*?</hudson\.model\.\w+ParameterDefinition>',
                ]
                for pattern in patterns:
                    m = re.search(pattern, xml_text, re.DOTALL)
                    if m:
                        xml_text = xml_text[:m.start()] + xml_text[m.end():]
                        logger.info(f"[GENERATE] Removed parameter block (regex): {name}")
                        break
            return xml_text

    def _remove_step_blocks(self, xml_text: str) -> str:
        """Remove hudson.tasks.Shell blocks that contain the removal marker."""
        pattern = r'\s*<hudson\.tasks\.Shell>\s*<command>__HYDRA_REMOVE_STEP__</command>.*?</hudson\.tasks\.Shell>'
        xml_text = re.sub(pattern, '', xml_text, flags=re.DOTALL)
        return xml_text
