patha = "/usr/local/123.txt"

sup = ['.doc', '.docx', '.ppt', '.pptx', '.pdf', '.txt']

file_ext = patha.split('.')[-1]
print(file_ext)

print(patha.endswith(sup))