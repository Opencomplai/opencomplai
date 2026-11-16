# frozen_string_literal: true

class Opencomplai < Formula
  include Language::Python::Virtualenv

  desc "Command-line EU AI Act compliance checks for AI systems"
  homepage "https://opencomplai.com"
  url "https://files.pythonhosted.org/packages/source/o/opencomplai/opencomplai-0.16.0.tar.gz"
  # PLACEHOLDER: replace with the sdist sha256 at release (see packaging/homebrew/README.md)
  sha256 "0000000000000000000000000000000000000000000000000000000000000000"
  license "AGPL-3.0-only"

  depends_on "pkgconf" => :build
  depends_on "rust" => :build # pydantic-core and cryptography build from source
  depends_on "jpeg-turbo"
  depends_on "libffi"
  depends_on "libyaml"
  depends_on "openssl@3"
  depends_on "python@3.12"

  uses_from_macos "zlib"

  # RESOURCES: generated at release by brew update-python-resources

  def install
    virtualenv_install_with_resources
    # opencomplai-cli, a resource, installs the same opencomplai script first, so the helper
    # does not see it as new and links nothing.
    bin.install_symlink libexec/"bin/opencomplai" unless (bin/"opencomplai").exist?
  end

  test do
    assert_match version.to_s, shell_output("#{bin}/opencomplai --version")
  end
end
