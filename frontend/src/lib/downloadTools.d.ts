export function verifySha256File(
  file: File,
  expectedDigest: string,
): Promise<boolean>
