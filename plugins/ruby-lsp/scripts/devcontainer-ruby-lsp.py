#!/usr/bin/env python3
"""Run ruby-lsp inside a running devcontainer for a host-side LSP client.

Usage: devcontainer-ruby-lsp.py <main checkout> [ruby-lsp args...]

The client speaks host paths and the server sees container paths. Every
message is re-framed with host paths rewritten to container paths on the way
in, and back on the way out. Git worktrees nested inside the checkout are
excluded from indexing, so their symbols don't show up as duplicates.
"""
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


def nested_worktrees(toplevel):
    paths = [line.split(' ', 1)[1] for line in git('worktree', 'list', '--porcelain').splitlines()
             if line.startswith('worktree ')]
    nested = []
    for path in paths:
        path = os.path.realpath(path)
        if path != toplevel and path.startswith(toplevel + os.sep):
            nested.append(os.path.relpath(path, toplevel))
    return nested


def substitutions(host, container):
    pairs = {(host, container), (quote(host), quote(container))}
    # Match whole path segments only, so /repo does not rewrite /repo-other.
    return [(re.compile(re.escape(src.encode()) + rb'(?=[/"\\]|$)'), dst.encode()) for src, dst in pairs]


class Proxy:
    def __init__(self, main, toplevel):
        root = container_workspace(main)
        self.to_container = substitutions(main, root)
        self.to_host = substitutions(root, main)
        self.excluded = [f'{path}/**/*' for path in nested_worktrees(toplevel)]
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

    def inbound(self, body):
        message = json.loads(body)
        if message.get('method') == 'initialize' and self.excluded:
            params = message.setdefault('params', {})
            options = params.get('initializationOptions') or {}
            indexing = options.setdefault('indexing', {})
            indexing['excludedPatterns'] = indexing.get('excludedPatterns', []) + self.excluded
            params['initializationOptions'] = options
            body = json.dumps(message).encode()
        return self.rewrite(body, self.to_container)

    def outbound(self, body):
        return self.rewrite(body, self.to_host)

    @staticmethod
    def rewrite(body, rules):
        for pattern, replacement in rules:
            body = pattern.sub(replacement, body)
        return body


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


def main():
    main_folder = sys.argv[1]
    toplevel = os.path.realpath(git('rev-parse', '--show-toplevel'))
    proxy = Proxy(main_folder, toplevel)
    server = subprocess.Popen(proxy.command(sys.argv[2:]), stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    threading.Thread(target=pump, args=(sys.stdin.buffer, server.stdin, proxy.inbound), daemon=True).start()
    pump(server.stdout, sys.stdout.buffer, proxy.outbound)
    sys.exit(server.wait())


if __name__ == '__main__':
    main()
