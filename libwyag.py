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
    """Same as repo_path, but create dirname(*path) if absent. For example,
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



class GitObject (object):

    repo = None

    def __init__(self, repo, data=None):
        self.repo = repo

        if data != None:
            self.deserialize(data)

    def serialize(self):
        """This function MUST be implemented by subclassses.

        It must read the obkect's contens from self.data, a byte string, and
        do whaterver it takes to conber it into a meaningful representation.
        What exactly that means depends on each subclass."""

        raise Exception("Unimplemented!")

    def deserialize(self, data):
        raise Exception("Unimplemented!")



def object_find(repo, name, fmt=None, follow=True):
    return name



def object_read(repo, sha):
    """Read object object_id from Git repository repo. Return a GitObject
    whose exact type depends on the object."""

    path = repo_file(repo, "objects", sha[:2], sha[2:])

    with open(path, "rb") as f:
        raw = zlib.decompress(f.read())

        # read object type
        x = raw.find(b' ')
        fmt = raw[0:x]

        # read and validate  object size
        y = raw.find(b'\x00', x)
        size = int(raw[x:y].decode("ascii"))
        if size != len(raw)-y-1:
            raise Exception("Malformed object {}: bad length".format(sha))

        # pick correct constructor
        if fmt==b'commit' : c=GitCommit
        elif fmt==b'tree' : c=GitTree
        elif fmt==b'tag' : c=GitTag
        elif fmt==b'blob' : c=GitBlob
        else:
            raise Exception("Unknown type {} for object {}".format(fmt.decode("ascii"), sha))

        return c(repo, raw[y+1:])


def object_write(obj, actually_write=True):
    # serialize object data
    data = obj.serialize()
    
    # add header
    result = obj.fmt + b' ' + str(len(data)).encode() + b'\x00' + data

    # get hash
    sha = hashlib.sha1(result).hexdigest()

    if actually_write:
        # compute path
        path = repo_file(obj.repo, "objects", sha[:2], sha[2:], mkdir=actually_write)

        with open(path, 'wb') as f:
            # compress and write
            f.write(zlib.compress(result))

    return sha


class GitBlob(GitObject):
    fmt=b'blob'

    def serialize(self):
        return self.blobdata

    def deserialize(self, data):
        self.blobdata = data

