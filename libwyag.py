import collections
import configparser
import hashlib
import os
import re
import zlib

git_folder = ".wyag" # ".git"


class GitRepository(object):
    """A git repository"""

    worktree = None
    gitdir = None
    conf = None


    def __init__(self, path, force=False):
        self.worktree = path
        self.gitdir = os.path.join(path, git_folder)

        if not (force or os.path.isdir(self.gitdir)):
            raise Exception("Not a Git repository {:s}".format(self.worktree))

        # read configuration file .git/config
        self.conf = configparser.ConfigParser()
        cf = repo_file(self, "config")

        if cf and os.path.exists(cf):
            self.conf.read([cf])
        elif not force:
            raise Exception("Configuration file is missing")

        if not force:
            vers = int(self.conf.get("core", "repositoryformatversion"))
            if vers != 0:
                raise Exception("Unsupported repositoryformatversion {}".format(vers))


def repo_path(repo, *path):
    """Comput path under repo's gitdir"""
    return os.path.join(repo.gitdir, *path)

def repo_file(repo, *path, mkdir=False):
    """Same as repo_path, but create dirname(*paht) if asent. For example,
    repo_file(r, refs, remotes, origin, HEAD) will create .git/refs/remotes/origin."""

    if repo_dir(repo, *path[:-1], mkdir=mkdir):
        return repo_path(repo, *path)

def repo_dir(repo, *path, mkdir=False):
    """Same as repo_path, but mkdir *path if absent if mkdir."""

    path = repo_path(repo, *path)

    if os.path.exists(path):
        if os.path.isdir(path):
            return path
        else:
            raise Exception("Not a directory {}".format(path))

    if mkdir:
        os.makedirs(path)
        return path
    else:
        return None


def repo_create(path):
    """Create a new repository at path."""

    repo = GitRepository(path, True)

    # make sure path doesn't exist or is empty

    if os.path.exists(repo.worktree):
        if not os.path.isdir(repo.worktree):
            raise Exception("{} is not a directroy".format(path))
        if os.listdir(repo.worktree):
            raise Exception("{} is not empty".format(path))
    else:
        os.makedirs(repo.worktree)

    assert(repo_dir(repo, "branches", mkdir=True))
    assert(repo_dir(repo, "objects", mkdir=True))
    assert(repo_dir(repo, "refs", "tags", mkdir=True))
    assert(repo_dir(repo, "refs", "head", mkdir=True))

    # .git/description
    with open(repo_file(repo, "description"), "w") as f:
        f.write("Unnamed repository; edit this file 'description' to name the repository.\n")

    # .git/HEAD
    with open(repo_file(repo, "HEAD"), "w") as f:
        f.write("refs: refs/heads/master\n")

    with open(repo_file(repo, "config"), "w") as f:
        config = repo_default_config()
        config.write(f)
    
    return repo


def repo_default_config():
    ret = configparser.ConfigParser()

    ret.add_section("core")
    ret.set("core", "repositoryformatversion", "0")
    ret.set("core", "filemode", "false")
    ret.set("core", "bare", "false")

    return ret


def repo_find(path=".", required=True):
    path = os.path.realpath(path)

    if os.path.isdir(os.path.join(path, git_folder)):
        return GitRepository(path)

    # search recursive in parent directories
    parent = os.path.realpath(os.path.join(path, ".."))

    if parent == path:
        # re reached root

        if required:
            raise Exception("No git repository")
        else:
            return None

    return repo_find(parent, required)

