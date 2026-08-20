# Code signing

Fidget's build script can produce a signed executable, but the certificate has
to be obtained first. This document covers what that involves and how to wire
it up once you have one.

## Why sign at all

An unsigned executable downloaded from the internet triggers Windows
SmartScreen — "Windows protected your PC" — and the user has to click through
*More info → Run anyway*. Signing with a publicly trusted certificate replaces
that with your verified name in the UAC prompt, and builds SmartScreen
reputation over time.

## Azure Artifact Signing

Microsoft's managed signing service, formerly called Trusted Signing. It is
the cheapest credible route for an individual developer: there is no hardware
token, certificates are issued on demand and are short-lived, and the private
key never leaves Microsoft's HSMs.

### Eligibility

Two things gate access, and they are worth checking *before* you start:

- **Location.** Public Trust certificates for individual developers are
  restricted to the **United States and Canada**. Organizations have a wider
  list (EU, UK, Australia, New Zealand, Japan, South Korea, Singapore,
  Switzerland, Norway, Israel).
- **Billing account type.** Identity details are pulled automatically from
  your Azure billing account, and the type must match: an **Individual**
  billing account can only be used for individual identity validation. Your
  legal name and address on that account must exactly match what you want on
  the certificate, because that is what gets issued.

### Setup

1. **Register the resource provider.** In the Azure portal, under your
   subscription → *Resource providers*, register `Microsoft.CodeSigning`.

2. **Create an Artifact Signing account.** Search for *Artifact Signing
   Accounts* → *Create*. Pick a region from the
   [supported list](https://learn.microsoft.com/en-us/azure/artifact-signing/quickstart)
   and note its endpoint URI (for example `https://eus.codesigning.azure.net`
   for East US) — the build script needs it.

3. **Complete identity validation.** This step is only possible in the portal,
   not the CLI, and only you can do it. Under *Objects → Identity validations*,
   switch the dropdown to **Individual**, then *New Identity → Public*.

   You will be asked to prove who you are through Microsoft's Verified ID
   partner (AU10TIX). In practice that means: a **government-issued photo ID**
   (passport, driving licence, or state ID), a phone number, and a **mobile
   device** to scan QR codes and photograph the document. You will also need
   the **Microsoft Authenticator** app to hold the resulting verified
   credential.

   The verification itself takes minutes. If additional documents are
   requested, expect days.

4. **Create a certificate profile.** Under *Objects → Certificate profiles* →
   *Create* → **Public Trust**, and select the completed identity validation.
   Note the profile name.

5. **Grant signing rights.** Assign the **Artifact Signing Certificate Profile
   Signer** role to whatever identity will run the build — your own account for
   local builds, or a service principal for CI.

## Signing locally

Install the Trusted Signing dlib that `signtool` loads:

```powershell
dotnet tool install --global Azure.CodeSigning.Client
```

Set these, then build with `-Sign`:

```powershell
$env:AZURE_TENANT_ID        = "<entra tenant id>"
$env:AZURE_CLIENT_ID        = "<service principal or app id>"
$env:AZURE_CLIENT_SECRET    = "<client secret>"
$env:TRUSTED_SIGNING_ENDPOINT = "https://eus.codesigning.azure.net"
$env:TRUSTED_SIGNING_ACCOUNT  = "<artifact signing account name>"
$env:TRUSTED_SIGNING_PROFILE  = "<certificate profile name>"
$env:TRUSTED_SIGNING_DLIB     = "<path to Azure.CodeSigning.Dlib.dll>"

.\packaging\build.ps1 -Version 1.0.0 -Sign
```

The script signs with SHA-256, timestamps against
`http://timestamp.acs.microsoft.com`, then verifies the signature before
packaging. Timestamping matters: it keeps the signature valid after the
certificate expires.

## Signing in CI

`.github/workflows/release.yml` builds and signs on tag push. Add these
repository secrets and the signing step activates automatically; without them
the workflow still builds, just unsigned.

| Secret | Value |
|---|---|
| `AZURE_TENANT_ID` | Entra tenant ID |
| `AZURE_CLIENT_ID` | Service principal app ID |
| `AZURE_CLIENT_SECRET` | Service principal secret |
| `TRUSTED_SIGNING_ENDPOINT` | Region endpoint URI |
| `TRUSTED_SIGNING_ACCOUNT` | Artifact Signing account name |
| `TRUSTED_SIGNING_PROFILE` | Certificate profile name |

## Verifying a signed build

```powershell
signtool verify /pa /v .\build\dist\Fidget\Fidget.exe
```

A good result shows the certificate chain, your verified name as the subject,
and a timestamp. You can also right-click the exe → *Properties → Digital
Signatures*.

## Alternatives

If Azure Artifact Signing is not available to you — most commonly because you
are outside the US and Canada as an individual — the other options are a
traditional OV/EV certificate from a CA such as DigiCert, Sectigo, or SSL.com.
These cost substantially more per year and, since the CA/Browser Forum's 2023
key-storage rules, require the key to live on a hardware token or cloud HSM.
Sectigo and SSL.com both offer individual-developer certificates that Azure
does not.
