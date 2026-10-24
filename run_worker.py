"""
run_worker.py - Specialized worker for Mass Stopping Power (MSP) Simulation
"""
import argparse
import os
import sys
import time
import json
import random
import shutil
import subprocess
from pathlib import Path
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

import gdrive_helper
from googleapiclient.http import MediaFileUpload

def parse_args():
    parser = argparse.ArgumentParser(description="MSP Swarm Worker")
    parser.add_argument("--runner-id", type=int, required=True)
    parser.add_argument("--num-runners", type=int, default=10)
    parser.add_argument("--primaries", type=int, default=100000)
    parser.add_argument("--gdrive-folder", type=str, required=True)
    parser.add_argument("--plan-file", type=str, default="plan_swarm.json")
    parser.add_argument("--manifest-file", type=str, default="manifest.csv")
    parser.add_argument("--github-user", type=str, default=None)
    parser.add_argument("--sim-bin", type=str, default="./build/Sim")
    return parser.parse_args()

def upload_file_to_drive(service, file_path: Path, parent_folder_id: str):
    q = f"'{parent_folder_id}' in parents and name = '{file_path.name}' and trashed = false"
    for attempt in range(5):
        try:
            res = service.files().list(q=q, supportsAllDrives=True, includeItemsFromAllDrives=True, fields="files(id)").execute().get("files", [])
            media = MediaFileUpload(str(file_path), resumable=True)
            if res:
                f_id = res[0]["id"]
                service.files().update(fileId=f_id, media_body=media, supportsAllDrives=True).execute()
                return f_id
            body = {"name": file_path.name, "parents": [parent_folder_id]}
            new_f = service.files().create(body=body, media_body=media, supportsAllDrives=True, fields="id").execute()
            return new_f["id"]
        except Exception:
            time.sleep(1.0 + random.uniform(0.5, 2.0))
    raise RuntimeError(f"Failed to upload {file_path.name}")

def main():
    args = parse_args()
    acc_name = args.github_user or os.environ.get("GITHUB_REPOSITORY_OWNER") or "runner"
    print("=" * 80)
    print(f"STARTING MSP GEANT4 RUNNER #{args.runner_id} (Account: {acc_name})")
    print("=" * 80)

    sim_bin = Path(args.sim_bin)
    if not sim_bin.exists():
        raise FileNotFoundError(f"Sim binary not found: {sim_bin}")

    service = gdrive_helper.get_drive_service()
    with open("drive_folders.json", "r", encoding="utf-8") as f:
        cf = json.load(f)
    flux_sub_map = cf.get("flux_subfolders", {})
    outputs_sub_map = cf.get("outputs_subfolders", {})

    with open(args.plan_file, "r", encoding="utf-8") as f:
        full_plan = json.load(f)
    my_jobs = full_plan.get(acc_name, {}).get(str(args.runner_id), [])

    print(f"Assigned {len(my_jobs)} MSP jobs to runner #{args.runner_id}:")
    for j in my_jobs:
        print(f"  * {j['job_name']}")

    if not my_jobs:
        print("No jobs for this runner. Exiting cleanly.")
        return

    for idx, job in enumerate(my_jobs, 1):
        job_name = job["job_name"]
        sample = job["sample"]
        macro_name = job["macro_file"]
        csv_filename = job["csv_filename"]
        dest_flux_folder = flux_sub_map[sample]
        dest_outputs_folder = outputs_sub_map[sample]

        # Check if already on Drive
        is_on_drive = False
        try:
            q_chk = f"'{dest_flux_folder}' in parents and name = '{csv_filename}' and trashed = false"
            res = service.files().list(q=q_chk, supportsAllDrives=True, includeItemsFromAllDrives=True, fields="files(id)").execute().get("files", [])
            if res:
                is_on_drive = True
        except Exception:
            pass

        if is_on_drive:
            print(f"[{idx}/{len(my_jobs)}] SKIP: {job_name} already on Drive.")
            continue

        print(f"[{idx}/{len(my_jobs)}] Executing MSP job: {job_name} (Macro: {macro_name})")
        msp_csv = Path("msp_results.csv")
        if msp_csv.exists():
            msp_csv.unlink()

        t0 = time.time()
        res_run = subprocess.run([str(sim_bin.resolve()), macro_name], capture_output=True, text=True)
        t_run = time.time() - t0

        if res_run.returncode != 0:
            print(f"  [ERROR] Execution failed for {macro_name} (code {res_run.returncode})")
            print(res_run.stderr[-1000:])
            continue

        print(f"  * MSP Sim run completed in {t_run:.2f} s")

        if not msp_csv.exists():
            print(f"  [ERROR] msp_results.csv not created!")
            continue

        local_out = Path(csv_filename)
        shutil.copy2(msp_csv, local_out)

        upload_file_to_drive(service, local_out, dest_flux_folder)
        print(f"  * Uploaded -> 02_Flux_Data/{sample}/{csv_filename}")
        local_out.unlink()
        msp_csv.unlink()

        # Upload any generated root files
        for root_f in Path(".").glob("msp_*.root"):
            upload_file_to_drive(service, root_f, dest_outputs_folder)
            print(f"  * Uploaded ROOT -> 03_Simulation_Outputs/{sample}/{root_f.name}")
            root_f.unlink()

    print(f"RUNNER #{args.runner_id} COMPLETED ALL ASSIGNED JOBS!")

if __name__ == "__main__":
    main()
