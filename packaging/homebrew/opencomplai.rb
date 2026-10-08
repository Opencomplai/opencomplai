# frozen_string_literal: true

class Opencomplai < Formula
  include Language::Python::Virtualenv

  desc "EU AI Act compliance checks for AI systems, from the command line"
  homepage "https://opencomplai.com"
  url "https://files.pythonhosted.org/packages/source/o/opencomplai/opencomplai-0.9.1.tar.gz"
  # PLACEHOLDER: replace with the sdist sha256 at release (see packaging/homebrew/README.md)
  sha256 "0000000000000000000000000000000000000000000000000000000000000000"
  license "AGPL-3.0-only"

  depends_on "python@3.12"

  # RESOURCES: generated at release by brew update-python-resources

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match version.to_s, shell_output("#{bin}/opencomplai --version")
  end
end
