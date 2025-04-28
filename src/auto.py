import subprocess

#order
scripts = [
    "data_collection/scrape_trade_show_vendors.py",
    "lead_generation/scraper.py",
    "lead_generation/ranker.py",
    "lead_management/lead_info.py"
]

for script in scripts:
    print(f"Running {script}...")
    result = subprocess.run(["python", script])

    if result.returncode != 0:
        print(f"Error: {script} exited with code {result.returncode}")
        break  # Stop running if any script fails
    else:
        print(f"{script} finished successfully.\n")
