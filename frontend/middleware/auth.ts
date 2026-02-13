export default defineNuxtRouteMiddleware((to) => {
  const auth = useAuthNew()

  const publicRoutes = ['/login', '/register']

  if (!auth.isAuthenticated.value && !publicRoutes.includes(to.path)) {
    return navigateTo('/login')
  }

  if (auth.isAuthenticated.value && publicRoutes.includes(to.path)) {
    return navigateTo('/')
  }
})
