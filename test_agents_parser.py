from agents_parser import AgentsManifest

manifest = AgentsManifest(".")
print("Fallback for 'Run unit tests':", manifest.get_fallback("Please run unit tests."))
print("Fallback for 'Build Android APK':", manifest.get_fallback("Please build android apk."))
