# Exchange intermediate certificates

DSE and CSE currently omit an intermediate CA certificate from their HTTPS
responses. These public CA certificates complete each server's published chain
while preserving certificate and hostname verification.

| File | Published by | Source | SHA-256 | Expires |
| --- | --- | --- | --- | --- |
| `sectigo-dv-r36.pem` | Sectigo | `http://crt.sectigo.com/SectigoPublicServerAuthenticationCADVR36.crt` | `8C:54:C3:34:B6:6B:A4:E4:26:77:2A:F4:A3:F9:13:6C:19:A1:AE:C7:29:FD:B2:8C:53:5C:07:A5:A4:EF:22:E0` | 2036-03-21 |
| `globalsign-r3-dv-2020.pem` | GlobalSign | `http://secure.globalsign.com/cacert/gsgccr3dvtlsca2020.crt` | `76:25:38:43:95:09:C4:11:C4:37:D3:C5:67:56:3E:13:78:67:12:81:FC:4A:14:64:AD:D0:31:87:08:43:67:6E` | 2029-03-18 |

The custom SSL contexts are mounted only for the exact official exchange host.
When an exchange fixes its server chain, remove the corresponding adapter and
certificate after confirming normal verification succeeds in deployment.
