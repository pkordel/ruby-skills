#!/usr/bin/env python3
"""Sit between an LSP client and ruby-lsp, excluding nested git worktrees.

Usage:
  ruby-lsp-proxy.py --devcontainer <main checkout> [ruby-lsp args...]
  ruby-lsp-proxy.py -- <server command...>

Git worktrees nested inside the checkout are excluded from indexing, so their
symbols don't show up as duplicates. ruby-lsp searches every file for
references regardless, so results located in them are dropped on the way out.

With --devcontainer, ruby-lsp runs inside the project's running devcontainer.
The client speaks host paths and the server sees container paths. Every
message is re-framed with host paths rewritten to container paths on the way
in, and back on the way out.

With --, the server command runs as is. Without nested worktrees there is
nothing to rewrite, so the proxy replaces itself with the command.
"""
import glob
import json
import os
import re
import subprocess
import sys
import threading
from urllib.parse import quote


def git(*args):
    return subprocess.run(['git', *args], capture_output=True, text=True, check=True).stdout.strip()


def container_workspace(main):
    out = subprocess.run(
        ['devcontainer', 'read-configuration', '--workspace-folder', main],
        capture_output=True, text=True, check=True,
    ).stdout
    return json.loads(out)['workspace']['workspaceFolder']


def worktree_path(toplevel, recorded, name):
    """Where a linked worktree lives under toplevel, relative to it, or None.

    Git records the path a worktree was created with. Inside a container that
    is often a host path, so also try each trailing part of it under toplevel,
    longest first, and accept a directory whose .git file points back at this
    worktree's admin directory.
    """
    path = os.path.realpath(recorded)
    if path.startswith(toplevel + os.sep):
        return os.path.relpath(path, toplevel)
    parts = recorded.strip(os.sep).split(os.sep)
    for i in range(1, len(parts)):
        relative = os.path.join(*parts[i:])
        try:
            with open(os.path.join(toplevel, relative, '.git')) as f:
                gitdir = f.read().strip()
        except OSError:
            continue
        if gitdir.rstrip('/').endswith(f'/worktrees/{name}'):
            return relative
    return None


def nested_worktrees(toplevel):
    common = os.path.realpath(git('rev-parse', '--path-format=absolute', '--git-common-dir'))
    nested = []
    for gitdir_file in sorted(glob.glob(os.path.join(common, 'worktrees', '*', 'gitdir'))):
        with open(gitdir_file) as f:
            recorded = os.path.dirname(f.read().strip())
        name = os.path.basename(os.path.dirname(gitdir_file))
        relative = worktree_path(toplevel, recorded, name)
        if relative:
            nested.append(relative)
    return nested


def substitutions(host, container):
    pairs = {(host, container), (quote(host), quote(container))}
    # Match whole path segments only, so /repo does not rewrite /repo-other.
    return [(re.compile(re.escape(src.encode()) + rb'(?=[/"\\]|$)'), dst.encode()) for src, dst in pairs]


def location_uri(item):
    if not isinstance(item, dict):
        return None
    return item.get('uri') or item.get('targetUri') or (item.get('location') or {}).get('uri')


class Proxy:
    def __init__(self, toplevel, server_toplevel=None):
        nested = nested_worktrees(toplevel)
        self.excluded = [f'{path}/**/*' for path in nested]
        # URIs as the server writes them, before any rewriting back to the client.
        server_toplevel = server_toplevel or toplevel
        self.excluded_uris = tuple(f'file://{quote(os.path.join(server_toplevel, path))}/' for path in nested)
        self.to_server = []
        self.to_client = []

    def inbound(self, body):
        message = json.loads(body)
        if message.get('method') == 'initialize' and self.excluded:
            params = message.setdefault('params', {})
            options = params.get('initializationOptions') or {}
            indexing = options.setdefault('indexing', {})
            indexing['excludedPatterns'] = indexing.get('excludedPatterns', []) + self.excluded
            params['initializationOptions'] = options
            body = json.dumps(message).encode()
        return self.rewrite(body, self.to_server)

    def outbound(self, body):
        if self.excluded_uris and b'"result"' in body:
            message = json.loads(body)
            result = message.get('result')
            if isinstance(result, list):
                kept = [item for item in result if not (location_uri(item) or '').startswith(self.excluded_uris)]
                if len(kept) != len(result):
                    message['result'] = kept
                    body = json.dumps(message).encode()
        return self.rewrite(body, self.to_client)

    @staticmethod
    def rewrite(body, rules):
        for pattern, replacement in rules:
            body = pattern.sub(replacement, body)
        return body


class DevcontainerProxy(Proxy):
    def __init__(self, main, toplevel):
        root = container_workspace(main)
        super().__init__(toplevel, root + toplevel[len(main):])
        self.to_server = substitutions(main, root)
        self.to_client = substitutions(root, main)
        self.container_cwd = root + toplevel[len(main):]
        self.env = []
        git_dir = os.path.realpath(git('rev-parse', '--absolute-git-dir'))
        if toplevel != main:
            # A worktree's .git file points at a host path; give git the container one.
            self.env = [f'GIT_DIR={root}{git_dir[len(main):]}', f'GIT_WORK_TREE={self.container_cwd}']
        self.main = main

    def command(self, args):
        cmd = ['devcontainer', 'exec', '--workspace-folder', self.main]
        for assignment in self.env:
            cmd += ['--remote-env', assignment]
        launch = 'cd "$1"; shift; command -v ruby-lsp >/dev/null && exec ruby-lsp "$@"; exec bundle exec ruby-lsp "$@"'
        return cmd + ['bash', '-lc', launch, 'ruby-lsp', self.container_cwd, *args]


def pump(src, dst, transform):
    while True:
        headers = {}
        while True:
            line = src.readline()
            if not line:
                dst.close()
                return
            line = line.strip()
            if not line:
                break
            name, _, value = line.decode('ascii').partition(':')
            headers[name.strip().lower()] = value.strip()
        body = transform(src.read(int(headers['content-length'])))
        dst.write(b'Content-Length: %d\r\n\r\n' % len(body) + body)
        dst.flush()


def local_proxy():
    try:
        return Proxy(os.path.realpath(git('rev-parse', '--show-toplevel')))
    except (OSError, subprocess.CalledProcessError):
        return None  # Not a git checkout, or git can't read it: nothing to exclude.


def main():
    if sys.argv[1:2] == ['--devcontainer'] and len(sys.argv) > 2:
        toplevel = os.path.realpath(git('rev-parse', '--show-toplevel'))
        proxy = DevcontainerProxy(sys.argv[2], toplevel)
        command = proxy.command(sys.argv[3:])
    elif sys.argv[1:2] == ['--'] and len(sys.argv) > 2:
        command = sys.argv[2:]
        proxy = local_proxy()
        if proxy is None or not proxy.excluded:
            os.execvp(command[0], command)
    else:
        sys.exit(__doc__.split('\n\n')[1])
    server = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    threading.Thread(target=pump, args=(sys.stdin.buffer, server.stdin, proxy.inbound), daemon=True).start()
    pump(server.stdout, sys.stdout.buffer, proxy.outbound)
    # os._exit: the stdin thread may still be blocked in a read, which makes a
    # normal interpreter shutdown abort.
    os._exit(server.wait())


if __name__ == '__main__':
    main()
