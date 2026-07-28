#!/usr/bin/env python3
"""Root launcher for Jenkins Job Configuration Manager."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "JenkinsJobConfiguration"))

from jenkins_job_manager_gui import main

if __name__ == "__main__":
    main()
