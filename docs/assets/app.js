(() => {
  const tabContainers = document.querySelectorAll('[data-tabs]');
  tabContainers.forEach((container) => {
    const tabs = Array.from(container.querySelectorAll('.tab'));
    const section = container.closest('.card');
    const panels = section ? Array.from(section.querySelectorAll('.tab-panel')) : [];

    tabs.forEach((tab) => {
      tab.addEventListener('click', () => {
        const key = tab.getAttribute('data-tab');
        tabs.forEach((item) => item.classList.toggle('active', item === tab));
        panels.forEach((panel) => panel.classList.toggle('active', panel.getAttribute('data-panel') === key));
      });
    });
  });

  const copyButtons = document.querySelectorAll('.copy-btn');
  copyButtons.forEach((btn) => {
    btn.addEventListener('click', async () => {
      const block = btn.closest('.cmd-block');
      const code = block ? block.querySelector('code') : null;
      if (!code) return;
      try {
        await navigator.clipboard.writeText(code.textContent || '');
        const old = btn.textContent;
        btn.textContent = '已复制';
        btn.classList.add('copied');
        setTimeout(() => {
          btn.textContent = old || '复制';
          btn.classList.remove('copied');
        }, 1200);
      } catch (_err) {
        btn.textContent = '复制失败';
      }
    });
  });

  const configInput = document.getElementById('g-config');
  const profileSelect = document.getElementById('g-profile');
  const stageSelect = document.getElementById('g-stage');
  const coresInput = document.getElementById('g-cores');
  const dryCheck = document.getElementById('g-dry');
  const buildBtn = document.getElementById('g-build');
  const output = document.getElementById('g-output');

  const buildCommand = () => {
    if (!output) return;
    const config = (configInput?.value || 'config/pipeline.yaml').trim();
    const profile = (profileSelect?.value || 'local').trim();
    const stage = (stageSelect?.value || 'all').trim();
    const cores = (coresInput?.value || '').trim();
    const dry = !!dryCheck?.checked;

    const parts = [
      'PYTHONPATH=src',
      'python -m gmv.cli run',
      `--config ${config}`,
      `--profile ${profile}`,
      `--stage ${stage}`,
    ];

    if (cores) {
      parts.push(`--cores ${cores}`);
    }
    if (dry) {
      parts.push('--dry-run');
    }

    output.textContent = parts.join(' ');
  };

  if (buildBtn) {
    buildBtn.addEventListener('click', buildCommand);
  }
})();
