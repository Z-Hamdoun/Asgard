import subprocess

def run_service(name: str) -> None:
    """Lance un service indépendant du Python
    
    Args:
        name (str): Nom du service.
    """
    subprocess.run(
        ['sudo', 'systemctl', 'start', f'{name}.service'],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
