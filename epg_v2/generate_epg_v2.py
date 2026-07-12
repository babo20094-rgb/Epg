#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
EPG V2
Eigene XMLTV-Engine

Unterstützte Länder:
- Deutschland
- Österreich
- Schweiz
- ExYu
- UK
- USA

Version: 2.0
"""

import requests
import gzip
import xml.etree.ElementTree as ET
from datetime import datetime

print("Starte EPG V2...")