# Template for Formula/shellglot.rb in github.com/Chuwee/homebrew-shellglot.
# The release workflow fills in @VERSION@ and @SHA256@ and pushes it to the tap.
class Shellglot < Formula
  desc "Shell command suggestions from plain words, with every part explained"
  homepage "https://github.com/Chuwee/shellglot"
  url "https://github.com/Chuwee/shellglot/archive/refs/tags/v@VERSION@.tar.gz"
  sha256 "@SHA256@"
  license "MIT"

  depends_on "python@3.13"

  # The anthropic provider needs the Anthropic Python SDK, installed from PyPI into a private virtualenv.
  allow_network_access! :build

  def install
    python = Formula["python@3.13"].opt_bin/"python3.13"
    system python, "-m", "venv", libexec
    system libexec/"bin/pip", "install", "--quiet", "anthropic==2.3.0"
    system "make", "install", "PREFIX=#{prefix}", "PYTHON=#{libexec}/bin/python"
  end

  def caveats
    <<~EOS
      Run `shellglot <what you want to do>`; the command you pick is copied to the clipboard.
      To get picks straight onto your prompt instead, add this to ~/.zshrc (or ~/.bashrc, with "bash"):
        eval "$(shellglot init zsh)"
    EOS
  end

  test do
    assert_match version.to_s, shell_output("#{bin}/shellglot --version")
    assert_match "shellglot.sh", shell_output("#{bin}/shellglot init zsh")
  end
end
