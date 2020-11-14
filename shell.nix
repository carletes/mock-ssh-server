let
  sources = import ./.nix/sources.nix;
  pkgs = import sources.nixpkgs {};

  # Drive `tox` using latest Python version.
  toxEnv = pkgs.python39.withPackages (ps: with ps; [
      tox
      setuptools
    ]);
in
pkgs.mkShell {
  buildInputs = [
    toxEnv

    # Python versions for `tox` to use.
    pkgs.python27
    pkgs.python36
    pkgs.python37
    pkgs.python38
    pkgs.python39

    # Keep this line if you use bash.
    pkgs.bashInteractive
  ];
}
