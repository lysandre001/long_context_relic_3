#!/usr/bin/env python3
"""
Test script to generate and display the final prompts for Task 1-4.
This script reads one row from the input CSV, loads the books JSON, and constructs
the prompts exactly as run_inference.py would do for each task type.
"""
import sys
import os
import json
import pandas as pd
from pathlib import Path

# Add parent directory to path to import from scripts
sys.path.append(str(Path(__file__).parent.parent))
from scripts.run_inference import construct_prompt
from scripts.prompts import PROMPT_REGISTRY

# Default prompt version for each task
DEFAULT_PROMPT_VERSIONS = {
    1: "v1_relic_simple",
    2: "v1_text_simple",
    3: "v1_line_simple",
    4: "v1",
}


def main():
    # Default paths (can be overridden via command line)
    input_csv = Path(__file__).parent.parent / "data" / "Aeneid_commentary_Conington.csv"
    books_json = Path(__file__).parent.parent / "data" / "relic_book_sentences_aeneid.json"
    output_dir = Path(__file__).parent / "prompt_output"
    
    # Allow override via command line
    if len(sys.argv) > 1:
        input_csv = Path(sys.argv[1])
    if len(sys.argv) > 2:
        books_json = Path(sys.argv[2])
    
    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load CSV and get first row
    print(f"Loading CSV from: {input_csv}")
    df = pd.read_csv(input_csv)
    if len(df) == 0:
        print("Error: CSV file is empty")
        sys.exit(1)
    
    row = df.iloc[0]
    print(f"Using row 0:")
    print(f"  UUID: {row.get('uuid', 'N/A')}")
    print(f"  Book: {row.get('book_title', 'N/A')}")
    print(f"  Commenter: {row.get('commenter', 'N/A')}")
    print()
    
    # Load books JSON
    print(f"Loading books JSON from: {books_json}")
    with open(books_json, 'r', encoding='utf-8') as f:
        books_data = json.load(f)
    print(f"Loaded {len(books_data)} book(s)")
    print()
    
    # Show available prompt versions for each task
    print("=" * 80)
    print("AVAILABLE PROMPT VERSIONS:")
    print("=" * 80)
    for task_key, versions in PROMPT_REGISTRY.items():
        version_list = list(versions.keys())
        print(f"  {task_key}: {version_list}")
    print()
    
    # Construct prompts for all tasks
    all_prompts = {}
    
    for task_type in [1, 2, 3, 4]:
        prompt_version = DEFAULT_PROMPT_VERSIONS[task_type]
        task_key = f"task{task_type}"
        
        print(f"Constructing prompt for Task {task_type} with version '{prompt_version}'...")
        try:
            prompt = construct_prompt(row, task_type, prompt_version, books_data)
            all_prompts[task_type] = {
                "version": prompt_version,
                "prompt": prompt,
                "status": "success"
            }
            print(f"  ✓ Task {task_type} prompt constructed successfully")
            
        except Exception as e:
            all_prompts[task_type] = {
                "version": prompt_version,
                "prompt": None,
                "status": "error",
                "error": str(e)
            }
            print(f"  ✗ Task {task_type} error: {e}")
    
    print()
    
    # Write all prompts to separate output files and display them
    for task_type, data in all_prompts.items():
        output_file = output_dir / f"task{task_type}_prompt_example.txt"
        
        print("=" * 80)
        print(f"TASK {task_type} PROMPT (version: {data['version']})")
        print("=" * 80)
        
        if data["status"] == "success":
            # Write to file
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"# Task {task_type} - Prompt Version: {data['version']}\n")
                f.write(f"# Status: {data['status']}\n")
                f.write("#" + "=" * 79 + "\n\n")
                f.write(data["prompt"])
            
            print(f"Output written to: {output_file}")
            print(f"Prompt length: {len(data['prompt'])} characters")
            print("-" * 80)
            
            # Show first 2000 chars for brevity (full prompt in file)
            prompt_preview = data["prompt"]
            if len(prompt_preview) > 2000:
                print(prompt_preview[:2000])
                print(f"\n... [TRUNCATED - see {output_file} for full prompt] ...")
            else:
                print(prompt_preview)
        else:
            print(f"Error: {data.get('error', 'Unknown error')}")
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"# Task {task_type} - Prompt Version: {data['version']}\n")
                f.write(f"# Status: ERROR\n")
                f.write(f"# Error: {data.get('error', 'Unknown error')}\n")
        
        print()
    
    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    for task_type, data in all_prompts.items():
        status_icon = "✓" if data["status"] == "success" else "✗"
        prompt_len = len(data["prompt"]) if data["prompt"] else 0
        print(f"  Task {task_type} [{status_icon}]: version={data['version']}, chars={prompt_len}")
    print()
    print(f"All prompts written to: {output_dir}")


if __name__ == "__main__":
    main()
