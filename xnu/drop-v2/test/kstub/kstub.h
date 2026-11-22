#pragma once
/* Cabeceras SIMULADAS de XNU: solo los símbolos que usa herolte_drop.c, con las firmas copiadas de XNU 8796.141.3. */
#include <stdint.h>
#include <stddef.h>
#include <errno.h>
#include <string.h>
typedef int errno_t; typedef int boolean_t; typedef int kern_return_t; typedef int wait_result_t;
typedef long long off_t; typedef char *caddr_t; typedef uint64_t user_addr_t; typedef unsigned long vm_size_t;
struct vnode; typedef struct vnode *vnode_t; struct vfs_context; typedef struct vfs_context *vfs_context_t;
struct kauth_cred; typedef struct kauth_cred *kauth_cred_t; struct proc; typedef struct proc *proc_t;
struct mount; typedef struct mount *mount_t; struct thread; typedef struct thread *thread_t;
typedef void (*thread_continue_t)(void *, wait_result_t);
#define __unused __attribute__((unused))
#define NULLVP ((vnode_t)0)
#define KERN_SUCCESS 0
#define ALLPERMS 07777
#define O_CREAT 0x200
#define O_TRUNC 0x400
#define FREAD 1
#define FWRITE 2
#define MNT_WAIT 1
#define F_FULLFSYNC 51
#define IO_UNIT 1
#define Z_WAITOK 1
#define Z_ZERO 4
#define VDIR 2
#define CREATE 1
#define DELETE 2
#define OP_MKDIR 1
#define OP_UNLINK 2
#define LOCKPARENT 1
#define AUDITVNPATH1 2
enum uio_seg { UIO_USERSPACE, UIO_SYSSPACE }; enum uio_rw { UIO_READ, UIO_WRITE };
#define CAST_USER_ADDR_T(a) ((user_addr_t)(uintptr_t)(a))
struct nameidata { vnode_t ni_dvp, ni_vp; };
#define NDINIT(ndp, op, pop, flags, segflg, namep, ctx) do { (void)(ndp); (void)(op); (void)(pop); (void)(flags); (void)(segflg); (void)(namep); (void)(ctx); } while (0)
struct vnode_attr { uint64_t va_supported, va_active; int va_type, va_mode; uint64_t va_data_size; };
#define VATTR_INIT(v) do { (v)->va_supported = (v)->va_active = 0; } while (0)
#define VATTR_SET(v, a, x) do { (v)->a = (x); } while (0)
#define VATTR_WANTED(v, a) do { (void)(v); } while (0)
#define VATTR_IS_SUPPORTED(v, a) ((v)->va_supported & 1)
errno_t vnode_lookup(const char *path, int flags, vnode_t *vpp, vfs_context_t ctx);
errno_t vnode_open(const char *path, int fmode, int cmode, int flags, vnode_t *vpp, vfs_context_t ctx);
errno_t vnode_close(vnode_t vp, int flags, vfs_context_t ctx);
int vnode_getattr(vnode_t vp, struct vnode_attr *vap, vfs_context_t ctx);
int vnode_setattr(vnode_t vp, struct vnode_attr *vap, vfs_context_t ctx);
int vnode_get(vnode_t); int vnode_put(vnode_t vp); mount_t vnode_mount(vnode_t vp); int vfs_isrdonly(mount_t mp);
int vn_rdwr(enum uio_rw rw, struct vnode *vp, caddr_t base, int len, off_t offset, enum uio_seg segflg, int ioflg, kauth_cred_t cred, int *aresid, proc_t p);
errno_t VNOP_FSYNC(vnode_t vp, int waitfor, vfs_context_t ctx);
errno_t VNOP_IOCTL(vnode_t vp, unsigned long command, caddr_t data, int fflag, vfs_context_t ctx);
errno_t vn_remove(vnode_t dvp, vnode_t *vpp, struct nameidata *ndp, int32_t flags, struct vnode_attr *vap, vfs_context_t ctx);
int vn_mkdir(vnode_t dvp, vnode_t *vpp, struct nameidata *ndp, struct vnode_attr *vap, vfs_context_t ctx);
int namei(struct nameidata *ndp); void nameidone(struct nameidata *);
vfs_context_t vfs_context_kernel(void); kauth_cred_t vfs_context_ucred(vfs_context_t ctx); proc_t vfs_context_proc(vfs_context_t ctx);
void *kalloc_data(vm_size_t size, int flags); void kfree_data(void *elem, vm_size_t size);
int printf(const char *, ...); void delay(int usec);
boolean_t PE_parse_boot_argn(const char *arg_string, void *arg_ptr, int max_len);
int snprintf(char *, size_t, const char *, ...);
