#!/bin/bash
cd /home/creux/Documents/AI/VIFagent/
source .venv/bin/activate
python -m vif_agent.script.get_mappings $1 -f $2