<template>
    <div class="app-filantropia_solar">
        <router-view />
    </div>
</template>

<script>
export default {
    name: 'App',
}
</script>

<style lang="scss">
@import './style/_golden-brand.scss';

.app-filantropia_solar {
    width: 100%;
    height: calc(100vh - 50px);
    background-color: $cream-bg;
    overflow: hidden;
}
</style>
