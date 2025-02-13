from invoke import task
import shutil

@task
def clean(c):
    """Remove build artifacts"""
    shutil.rmtree("dist", ignore_errors=True)
    shutil.rmtree("*.egg-info", ignore_errors=True)

@task
def build(c):
    """Build wheel package"""
    c.run("poetry build")

@task
def docker_build(c, tag="latest"):
    """Build Docker image"""
    c.run(f"docker build -t mwl-provider:{tag} .")

@task(pre=[clean, build])
def full_build(c, tag="latest"):
    """Clean, build wheel, and build Docker image"""
    docker_build(c, tag)
