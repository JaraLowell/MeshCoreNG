Import("env")

env.Append(CPPDEFINES=[("FIRMWARE_TARGET", '\\"%s\\"' % env["PIOENV"])])
