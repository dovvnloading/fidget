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

## Signing in CI (recommended)

`.github/workflows/release.yml` builds and signs on tag push, using
`azure/artifact-signing-action` with **OpenID Connect**. GitHub mints a
short-lived token that Azure trusts directly, so there is no client secret to
store or rotate. Nothing needs installing locally, and Actions minutes are
free on public repositories.

### One-time Azure setup

1. **Register an app** in Microsoft Entra ID (*App registrations → New
   registration*). Note its **Application (client) ID** and your **Directory
   (tenant) ID**.

2. **Add a federated credential.** On the app → *Certificates & secrets →
   Federated credentials → Add credential*, choose **GitHub Actions deploying
   Azure resources**, then:

   | Field | Value |
   |---|---|
   | Organization | `dovvnloading` |
   | Repository | `fidget` |
   | Entity type | **Tag** |
   | Tag | `*` |

   Add a second credential with entity type **Branch** and branch `main` if you
   want `workflow_dispatch` runs to sign too.

3. **Grant signing rights.** On your Artifact Signing account → *Access control
   (IAM) → Add role assignment*, give the app the **Artifact Signing
   Certificate Profile Signer** role.

### Repository configuration

Under *Settings → Secrets and variables → Actions*:

**Secrets** — identifiers, kept out of logs:

| Secret | Value |
|---|---|
| `AZURE_CLIENT_ID` | Application (client) ID of the app registration |
| `AZURE_TENANT_ID` | Directory (tenant) ID |
| `AZURE_SUBSCRIPTION_ID` | Subscription holding the signing account |

**Variables** — non-sensitive, visible in logs for easier debugging:

| Variable | Example |
|---|---|
| `SIGNING_ENDPOINT` | `https://eus.codesigning.azure.net/` |
| `SIGNING_ACCOUNT` | Your Artifact Signing account name |
| `SIGNING_PROFILE` | Your certificate profile name |

The workflow keys off `AZURE_CLIENT_ID`: present, it signs; absent, it builds
unsigned and says so. Release with:

```powershell
git tag v1.0.1
git push origin v1.0.1
```

### What gets signed

Only `Fidget.exe`. The bundle also contains ~150 DLLs, but those are
third-party — WebView2, pythonnet, CPython — and already carry their vendors'
signatures. Re-signing would replace those signatures and consume signing
quota per file for no benefit. SmartScreen evaluates the executable the user
launches, which is the one that gets signed.

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
