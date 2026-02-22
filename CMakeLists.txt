cmake_minimum_required(VERSION 3.16)
project(webos_remote_media_support LANGUAGES C CXX)

include(ExternalProject)

# ===== Layout =====
# Deps live here (you said: lib/)
set(DEPS_DIR "${CMAKE_SOURCE_DIR}/lib")

# Build dir is "build/" (CMake -B build). Inside it:
set(SUPERBUILD_DIR "${CMAKE_BINARY_DIR}/_deps_build")

# Where compiled libs/headers will be installed (like jassub build/libraries)
set(PREFIX_DIR "${CMAKE_SOURCE_DIR}/build/libraries")

# Where the final executable should go
set(DIST_DIR "${CMAKE_SOURCE_DIR}/dist")

# Meta dirs for ExternalProject (stamp/tmp/prefix) in one place
set(EP_META_DIR "${CMAKE_BINARY_DIR}/_meta")

# Ensure folders exist
file(MAKE_DIRECTORY "${SUPERBUILD_DIR}")
file(MAKE_DIRECTORY "${EP_META_DIR}")
file(MAKE_DIRECTORY "${PREFIX_DIR}")
file(MAKE_DIRECTORY "${DIST_DIR}")
file(MAKE_DIRECTORY "${DIST_DIR}/bin")
file(MAKE_DIRECTORY "${DIST_DIR}/lib")

# ===== Profiles (dev/prod) =====
set(PROFILE "dev" CACHE STRING "Build profile: dev or prod")
set_property(CACHE PROFILE PROPERTY STRINGS dev prod)

if(PROFILE STREQUAL "prod")
  set(_cfg "release")
  set(_cmake_build_type "Release")
  set(_cflags   "-O3 -DNDEBUG")
  set(_cxxflags "-O3 -DNDEBUG")
else()
  set(_cfg "debug")
  set(_cmake_build_type "Debug")
  set(_cflags   "-O0 -g3")
  set(_cxxflags "-O0 -g3")
endif()

# ===== Tools =====
find_program(PKG_CONFIG_EXECUTABLE pkg-config REQUIRED)
find_program(PYTHON3_EXECUTABLE python3 REQUIRED)
find_program(MESON_EXECUTABLE meson REQUIRED)
find_program(NINJA_EXECUTABLE ninja REQUIRED)

# ===== Env for sub-builds (so they find PREFIX_DIR) =====
set(_env
  "PKG_CONFIG_PATH=${PREFIX_DIR}/lib/pkgconfig:${PREFIX_DIR}/lib64/pkgconfig"
  "CMAKE_PREFIX_PATH=${PREFIX_DIR}"
  "PATH=${PREFIX_DIR}/bin:$ENV{PATH}"
)

# ===== Helpers =====
# Meson caches options; we wipe the per-project build dir for reproducibility.
# IMPORTANT: ExternalProject does "cd BINARY_DIR" before running CONFIGURE_COMMAND,
# so BINARY_DIR must always exist. We use SUPERBUILD_DIR as BINARY_DIR and a subdir per project.
function(ep_meson name srcdir)
  set(extra_setup_args ${ARGN})
  set(_build_subdir "${SUPERBUILD_DIR}/${name}")

  ExternalProject_Add(${name}
    PREFIX     "${EP_META_DIR}/${name}"
    SOURCE_DIR "${srcdir}"
    BINARY_DIR "${SUPERBUILD_DIR}"
    CONFIGURE_COMMAND
      ${CMAKE_COMMAND} -E rm -rf "${_build_subdir}"
      COMMAND ${CMAKE_COMMAND} -E make_directory "${_build_subdir}"
      COMMAND ${CMAKE_COMMAND} -E env ${_env}
              ${MESON_EXECUTABLE} setup "${_build_subdir}" "${srcdir}"
                --prefix "${PREFIX_DIR}"
                --libdir "lib"
                --buildtype "${_cfg}"
                --default-library=static
                ${extra_setup_args}
    BUILD_COMMAND
      ${CMAKE_COMMAND} -E env ${_env}
      ${MESON_EXECUTABLE} compile -C "${_build_subdir}"
    INSTALL_COMMAND
      ${CMAKE_COMMAND} -E env ${_env}
      ${MESON_EXECUTABLE} install -C "${_build_subdir}"
    USES_TERMINAL_BUILD ON
  )
endfunction()

function(ep_cmake name srcdir)
  set(extra_cmake_args ${ARGN})
  ExternalProject_Add(${name}
    PREFIX     "${EP_META_DIR}/${name}"
    SOURCE_DIR "${srcdir}"
    BINARY_DIR "${SUPERBUILD_DIR}/${name}"
    CMAKE_ARGS
      -DCMAKE_INSTALL_PREFIX=${PREFIX_DIR}
      -DCMAKE_BUILD_TYPE=${_cmake_build_type}
      -DBUILD_SHARED_LIBS=OFF
      -DCMAKE_POSITION_INDEPENDENT_CODE=ON
      -DCMAKE_C_FLAGS=${_cflags}
      -DCMAKE_CXX_FLAGS=${_cxxflags}
      ${extra_cmake_args}
    BUILD_COMMAND
      ${CMAKE_COMMAND} --build "${SUPERBUILD_DIR}/${name}" --config ${_cmake_build_type}
    INSTALL_COMMAND
      ${CMAKE_COMMAND} --install "${SUPERBUILD_DIR}/${name}" --config ${_cmake_build_type}
    USES_TERMINAL_BUILD ON
  )
endfunction()

function(ep_autotools name srcdir)
  ExternalProject_Add(${name}
    PREFIX     "${EP_META_DIR}/${name}"
    SOURCE_DIR "${srcdir}"
    BINARY_DIR "${SUPERBUILD_DIR}/${name}"
    CONFIGURE_COMMAND
      ${CMAKE_COMMAND} -E make_directory "${SUPERBUILD_DIR}/${name}"
      COMMAND ${CMAKE_COMMAND} -E chdir "${srcdir}" ./bootstrap
      COMMAND ${CMAKE_COMMAND} -E chdir "${SUPERBUILD_DIR}/${name}"
        ${CMAKE_COMMAND} -E env ${_env} CFLAGS=-fPIC
        "${srcdir}/configure" --prefix=${PREFIX_DIR} --enable-static --disable-shared
    BUILD_COMMAND   ${CMAKE_COMMAND} -E env ${_env} make -C "${SUPERBUILD_DIR}/${name}"
    INSTALL_COMMAND ${CMAKE_COMMAND} -E env ${_env} make -C "${SUPERBUILD_DIR}/${name}" install
    USES_TERMINAL_BUILD ON
  )
endfunction()

function(find_deb_so pkg so_name out_var)
  execute_process(
    COMMAND /bin/sh -c "dpkg -L ${pkg} | grep -E '/${so_name}$' | head -n1"
    OUTPUT_VARIABLE _p
    OUTPUT_STRIP_TRAILING_WHITESPACE
  )
  if(NOT _p)
    message(FATAL_ERROR "No se encontró ${so_name} en el paquete ${pkg}")
  endif()
  set(${out_var} "${_p}" PARENT_SCOPE)
endfunction()

function(bundle_deb_so pkg so_name)
  find_deb_so(${pkg} ${so_name} _SO_PATH)
  add_custom_command(TARGET wrms_libass POST_BUILD
    COMMAND cp -vL "${_SO_PATH}" "${DIST_DIR}/lib/"
  )
endfunction()

# ===== Paths inside lib/ =====
set(PATH_BROTLI      "${DEPS_DIR}/brotli")
set(PATH_FREETYPE    "${DEPS_DIR}/freetype")
set(PATH_FRIBIDI     "${DEPS_DIR}/fribidi")
set(PATH_HARFBUZZ    "${DEPS_DIR}/harfbuzz")
set(PATH_FONTCONFIG  "${DEPS_DIR}/fontconfig")
set(PATH_LIBASS      "${DEPS_DIR}/libass")


# ===== Dependencies =====
ep_cmake(brotli_ep   "${PATH_BROTLI}")

# FreeType
ep_meson(freetype_ep  "${PATH_FREETYPE}"
  -Dbrotli=enabled
  -Dbzip2=enabled
  -Dharfbuzz=enabled
  -Dmmap=auto
  -Dpng=enabled
  -Dtests=disabled
  -Dzlib=enabled
)
add_dependencies(freetype_ep brotli_ep)

# FriBidi
ep_meson(fribidi_ep  "${PATH_FRIBIDI}"
  -Ddocs=false
  -Dtests=false
)
add_dependencies(fribidi_ep freetype_ep)

# HarfBuzz (mínimo para libass)
ep_meson(harfbuzz_ep "${PATH_HARFBUZZ}"
  -Dfreetype=enabled
  -Dtests=disabled
  -Dintrospection=disabled
  -Ddocs=disabled
  -Ddoc_tests=false
  -Dutilities=disabled
)
add_dependencies(harfbuzz_ep freetype_ep fribidi_ep)

# Fontconfig
ep_meson(fontconfig_ep "${PATH_FONTCONFIG}"
  -Ddoc=disabled
  -Dtests=disabled
  -Dtools=disabled
  -Dcache-build=enabled
  -Dxml-backend=expat
)
add_dependencies(fontconfig_ep freetype_ep)

# libass
ep_meson(libass_ep "${PATH_LIBASS}"
  -Dtest=disabled
  -Dcompare=disabled
  -Dprofile=disabled
  -Dfuzz=disabled
  -Dcheckasm=disabled
  -Dfontconfig=enabled
  -Dlibunibreak=enabled
)
add_dependencies(libass_ep freetype_ep fribidi_ep harfbuzz_ep fontconfig_ep)

# ===== Your app =====
# build a shared library instead of an executable
add_library(wrms_libass SHARED src/wrms_libass.cpp)
add_dependencies(wrms_libass libass_ep)

target_include_directories(wrms_libass PRIVATE "${PREFIX_DIR}/include")
target_link_directories(wrms_libass PRIVATE "${PREFIX_DIR}/lib" "${PREFIX_DIR}/lib64")

# Link transitive deps explicitly (helps when building static)
target_link_libraries(wrms_libass PRIVATE
  unibreak
  ass
  png
  z
  bz2
  brotlienc
  brotlidec
  brotlicommon
  freetype
  harfbuzz
  fribidi
  expat
  uuid
  fontconfig
)

execute_process(
  COMMAND ${CMAKE_COMMAND} -E env ${_env} ${PKG_CONFIG_EXECUTABLE} --static --libs libass freetype2 harfbuzz fribidi fontconfig
  OUTPUT_VARIABLE _PC_LIBS
  OUTPUT_STRIP_TRAILING_WHITESPACE
)
if(_PC_LIBS)
  separate_arguments(_PC_LIBS)
  target_link_libraries(wrms_libass PRIVATE ${_PC_LIBS})
endif()

# Put library in dist/bin
set_target_properties(wrms_libass PROPERTIES
  LIBRARY_OUTPUT_DIRECTORY "${DIST_DIR}/bin"
  ARCHIVE_OUTPUT_DIRECTORY "${DIST_DIR}/bin"
  RUNTIME_OUTPUT_DIRECTORY "${DIST_DIR}/bin"
  OUTPUT_NAME "wrms_libass"
  BUILD_WITH_INSTALL_RPATH TRUE
  INSTALL_RPATH "\$ORIGIN/../lib"
  INSTALL_RPATH_USE_LINK_PATH FALSE
)

bundle_deb_so(libuuid1     libuuid.so.1)
bundle_deb_so(libexpat1    libexpat.so.1)
bundle_deb_so(libpng16-16  libpng16.so.16)
bundle_deb_so(zlib1g       libz.so.1)
bundle_deb_so(libbz2-1.0   libbz2.so.1.0)
bundle_deb_so(libunibreak1 libunibreak.so.1)

message(STATUS "Profile: ${PROFILE}")
message(STATUS "Libraries prefix: ${PREFIX_DIR}")
message(STATUS "ExternalProject meta: ${EP_META_DIR}")
message(STATUS "Library output: ${DIST_DIR}/bin")
