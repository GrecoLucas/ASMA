-- prosody.cfg.lua
-- Minimal Prosody config for local SPADE development.
-- This file is mounted into the Docker container.

VirtualHost "localhost"
  allow_registration = true        -- lets SPADE auto-register agent JIDs
  authentication = "internal_plain"

  -- Required modules
  modules_enabled = {
    "roster";
    "saslauth";
    "dialback";
    "disco";
    "carbons";
    "pep";
    "private";
    "blocklist";
    "vcard4";
    "vcard_legacy";
    "version";
    "uptime";
    "time";
    "ping";
    "register";     -- in-band registration (XEP-0077)
    "admin_adhoc";
  }

  -- Disable TLS requirement so agents can connect without certificates
  c2s_require_encryption = false
  c2s_secure_auth = false
  s2s_require_encryption = false
